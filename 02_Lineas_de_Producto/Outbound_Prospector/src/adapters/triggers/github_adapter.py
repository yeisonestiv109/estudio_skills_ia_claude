"""
GitHubAdapter — implementación del PuertoFuenteTriggers.

Busca actividad de código en GitHub vinculada al dominio de la empresa objetivo:
repositorios recientes, issues abiertos y match con las tecnologías del ICP.

API pública (sin autenticación): 60 req/h para endpoints generales.
API de búsqueda: 10 req/min sin token, 30 req/min con token.

Estrategia de búsqueda:
    1. Extraer el nombre de la organización del dominio (acme.com → acme).
    2. GET /orgs/{org}/repos (fallback /users/{user}/repos) para ver si existe.
    3. VERIFICAR PROPIEDAD (anti-colisión de nombre): antes de aceptar los
       repos como señal de LA empresa, GET /orgs/{org} (fallback /users/{user})
       para leer el sitio web declarado por la org (campo `blog`) y comparar
       su dominio registrable contra empresa.dominio. Si no coinciden (o la
       org no declara sitio web), NO se confía en esos repos → [].
    4. Si la org pertenece a la empresa: analizar repos activos, filtrar por
       tecnologías del ICP.
    5. Generar Trigger según relevancia (repos activos con match → MEDIA).

Anti-colisión de nombre (bug de raíz corregido): _extraer_org_name toma el
nombre raíz del dominio y busca en GitHub por ese nombre. Colisiona con orgs
globales homónimas: "Forbes Colombia" (forbes.co) matcheaba la org GitHub
`forbes` (de forbes.com de EE.UU.); igual "portafolio", "bia". La verificación
de propiedad (paso 3) cierra ese hueco comparando el dominio del sitio web que
la PROPIA org de GitHub declara contra el dominio de la empresa buscada.

Costo de rate limit: la verificación agrega 1 request por empresa con org
candidata. Es aceptable — GitHub es un adaptador condicional (AdapterRouting
Policy solo lo activa para ciertas categorías) y de volumen bajo.

Manejo de rate limits:
    - HTTP 403 con X-RateLimit-Remaining: 0 → rate limit → retornar []
    - HTTP 404 → organización no existe → retornar [] silenciosamente
    - Cualquier otro error → retornar []

Contrato de error: NUNCA propaga excepciones al Core. Errores → [].
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime

import requests

from src.core.domain.dominio import mismo_dominio_base
from src.core.domain.models import (
    Empresa,
    NivelConfianza,
    OrigenTrigger,
    Trigger,
)
from src.core.domain.text_matching import contiene_palabra_completa
from src.core.ports.interfaces import PuertoFuenteTriggers

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_REQUEST_TIMEOUT_SECS = 12
_MAX_REPOS = 10

# Mapeo de extensiones/lenguajes GitHub al vocabulario del ICP
_LANGUAGE_MAP: dict[str, list[str]] = {
    "Python": ["python", "django", "flask", "fastapi"],
    "JavaScript": ["javascript", "node", "nodejs", "react", "vue", "angular"],
    "TypeScript": ["typescript", "ts", "next.js", "nestjs"],
    "Java": ["java", "spring", "quarkus"],
    "Go": ["go", "golang"],
    "Rust": ["rust"],
    "PHP": ["php", "laravel", "symfony"],
    "Ruby": ["ruby", "rails"],
    "C#": ["c#", "dotnet", ".net"],
    "Kotlin": ["kotlin", "android"],
    "Swift": ["swift", "ios"],
}


def _extraer_org_name(dominio: str) -> str:
    """
    Extrae el nombre de la organización de GitHub desde el dominio.
    acme.com → acme | my-company.co.uk → my-company | api.acme.io → acme
    """
    dominio = dominio.strip().lower()
    # Eliminar protocolo si está
    if "://" in dominio:
        dominio = dominio.split("://", 1)[1]
    # Quitar subdominios (www, api, etc.) y TLD
    partes = dominio.split(".")
    # Heurística: tomar la parte más larga que no sea TLD conocido
    tlds = {
        "com",
        "co",
        "org",
        "net",
        "io",
        "dev",
        "ai",
        "app",
        "uk",
        "us",
        "mx",
        "ar",
        "br",
    }
    candidatos = [p for p in partes if p not in tlds and len(p) > 1]
    return candidatos[0] if candidatos else partes[0]


def _parsear_fecha_github(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _match_tecnologias(
    lenguaje_repo: str | None, tecnologias_objetivo: list[str]
) -> bool:
    """
    Verifica si el lenguaje principal del repo hace match con el ICP, usando
    matching por PALABRA COMPLETA (evita el falso positivo "java" ⊂ "javascript").
    """
    if not lenguaje_repo:
        return False
    aliases = _LANGUAGE_MAP.get(lenguaje_repo, [])
    for tech in tecnologias_objetivo:
        # Match directo por palabra completa (ambas direcciones).
        if contiene_palabra_completa(lenguaje_repo, tech) or contiene_palabra_completa(
            tech, lenguaje_repo
        ):
            return True
        # Match vía mapa de aliases del lenguaje (alias como texto, tech como needle).
        if any(contiene_palabra_completa(alias, tech) for alias in aliases):
            return True
    return False


def _construir_headers(github_token: str | None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    return headers


class GitHubAdapter(PuertoFuenteTriggers):
    """
    Adaptador Motor 2 — Inteligencia de Código (GitHub).

    Busca actividad pública de la organización en GitHub para detectar:
    - Repos activos que usen tecnologías del ICP (señal de stack confirmado)
    - Issues abiertos en repos con deuda técnica (señal de dolor visible)

    Args:
        tecnologias_objetivo: Tecnologías del ManifiestoICP para match.
        github_token: Token personal de GitHub (opcional). Sin token: 60 req/h.
                      Con token: 5000 req/h. Lee de GITHUB_TOKEN si no se pasa.
        max_repos: Máximo de repos a analizar por organización.
    """

    def __init__(
        self,
        tecnologias_objetivo: list[str] | None = None,
        github_token: str | None = None,
        max_repos: int = _MAX_REPOS,
    ) -> None:
        self._tecnologias = tecnologias_objetivo or []
        self._token = github_token or os.getenv("GITHUB_TOKEN")
        self._max_repos = max_repos
        self._headers = _construir_headers(self._token)

    def obtener_triggers(self, empresa: Empresa) -> list[Trigger]:
        """
        Busca repos públicos de la organización del dominio de la empresa.
        Implementa PuertoFuenteTriggers.obtener_triggers().
        """
        if not empresa.dominio:
            return []

        org = _extraer_org_name(empresa.dominio)
        if not org:
            return []

        # Intentar como organización primero, luego como usuario. Se recuerda
        # cuál de los dos respondió para consultar el perfil correcto en la
        # verificación de propiedad (paso 3).
        repos = self._obtener_repos_org(org)
        es_org = repos is not None
        if repos is None:
            repos = self._obtener_repos_user(org)
        if not repos:
            return []

        # Verificación de propiedad (anti-colisión de nombre): solo se confía
        # en estos repos si la org/usuario declara un sitio web cuyo dominio
        # registrable coincide con el de la empresa buscada.
        if not self._org_pertenece_a_empresa(org, empresa.dominio, es_org):
            logger.info(
                "GitHub: org '%s' NO verificada como propiedad de '%s' "
                "(colisión de nombre no confirmada). Sin trigger.",
                org,
                empresa.dominio,
            )
            return []

        return self._analizar_repos(repos, empresa, org)

    def _obtener_repos_org(self, org: str) -> list[dict] | None:
        """Busca repos bajo /orgs/{org}/repos. Retorna None si no existe."""
        url = f"{_GITHUB_API}/orgs/{org}/repos"
        return self._get_repos(url)

    def _obtener_repos_user(self, user: str) -> list[dict] | None:
        """Fallback: busca repos bajo /users/{user}/repos."""
        url = f"{_GITHUB_API}/users/{user}/repos"
        return self._get_repos(url)

    def _get_repos(self, url: str) -> list[dict] | None:
        """Ejecuta la llamada HTTP con reintentos ante 429/5xx y maneja todos los errores."""
        params = {
            "sort": "updated",
            "direction": "desc",
            "per_page": str(self._max_repos),
            "type": "public",
        }
        _REINTENTABLES = {429, 500, 502, 503, 504}
        for intento in range(3):
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=self._headers,
                    timeout=_REQUEST_TIMEOUT_SECS,
                )
            except requests.exceptions.Timeout:
                logger.warning("GitHub: timeout en '%s'. Retornando None.", url)
                return None
            except requests.exceptions.RequestException as exc:
                logger.error("GitHub: error de red en '%s': %s", url, exc)
                return None

            if response.status_code == 404:
                logger.debug("GitHub: organización/usuario no encontrado en '%s'.", url)
                return None

            if response.status_code == 403:
                remaining = response.headers.get("X-RateLimit-Remaining", "?")
                if remaining == "0":
                    logger.warning("GitHub: rate limit alcanzado. Retornando None.")
                else:
                    logger.warning("GitHub: acceso prohibido (403) en '%s'.", url)
                return None

            if response.status_code in _REINTENTABLES and intento < 2:
                logger.warning(
                    "GitHub: HTTP %d en '%s'. Reintento en 2s...",
                    response.status_code,
                    url,
                )
                time.sleep(2)
                continue

            if response.status_code != 200:
                logger.warning(
                    "GitHub: HTTP %d en '%s'. Retornando None.",
                    response.status_code,
                    url,
                )
                return None

            try:
                return response.json()
            except Exception:
                return None

        return None

    def _org_pertenece_a_empresa(
        self, org: str, dominio_empresa: str, es_org: bool
    ) -> bool:
        """
        Verifica que la org/usuario de GitHub `org` realmente pertenezca a la
        empresa cuyo dominio es `dominio_empresa`, comparando el sitio web que
        la PROPIA org declara en su perfil (campo `blog`) contra el dominio de
        la empresa (por dominio registrable, vía mismo_dominio_base).

        Retorna True solo si el perfil declara un `blog` cuyo dominio base
        coincide con el de la empresa. Retorna False si:
            - el perfil no se pudo leer (404/403/red/error),
            - el perfil no declara `blog` (o está vacío),
            - el dominio del `blog` NO coincide con el de la empresa (colisión
              de nombre: ej. empresa forbes.co vs. org GitHub con blog
              forbes.com).

        Fail-closed: ante cualquier duda, NO se confía en la org (retorna
        False) — es preferible perder una señal de una org legítima sin blog
        declarado que atribuir a la empresa los repos de una org homónima
        ajena.
        """
        endpoint = "orgs" if es_org else "users"
        url = f"{_GITHUB_API}/{endpoint}/{org}"
        perfil = self._get_perfil(url)
        if not isinstance(perfil, dict):
            return False

        blog = perfil.get("blog")
        if not blog or not str(blog).strip():
            logger.debug(
                "GitHub: perfil de '%s' sin sitio web declarado (blog). "
                "No verificable.",
                org,
            )
            return False

        coincide = mismo_dominio_base(str(blog), dominio_empresa)
        if not coincide:
            logger.debug(
                "GitHub: sitio web de la org '%s' (%s) no coincide con el "
                "dominio de la empresa (%s). Posible colisión de nombre.",
                org,
                blog,
                dominio_empresa,
            )
        return coincide

    def _get_perfil(self, url: str) -> dict | None:
        """
        GET del perfil de una org/usuario de GitHub. Retorna el dict del
        perfil, o None ante 404/403/red/no-200/JSON inválido.

        Mismo contrato de error que _get_repos (nunca propaga; 403 rate-limit
        → None), pero sin los params de listado de repos ni reintentos: es una
        sola lectura de metadatos.
        """
        try:
            response = requests.get(
                url,
                headers=self._headers,
                timeout=_REQUEST_TIMEOUT_SECS,
            )
        except requests.exceptions.Timeout:
            logger.warning("GitHub: timeout leyendo perfil '%s'. Retornando None.", url)
            return None
        except requests.exceptions.RequestException as exc:
            logger.error("GitHub: error de red leyendo perfil '%s': %s", url, exc)
            return None

        if response.status_code == 404:
            logger.debug("GitHub: perfil no encontrado en '%s'.", url)
            return None

        if response.status_code == 403:
            remaining = response.headers.get("X-RateLimit-Remaining", "?")
            if remaining == "0":
                logger.warning(
                    "GitHub: rate limit alcanzado (perfil). Retornando None."
                )
            else:
                logger.warning("GitHub: acceso prohibido (403) en perfil '%s'.", url)
            return None

        if response.status_code != 200:
            logger.warning(
                "GitHub: HTTP %d leyendo perfil '%s'. Retornando None.",
                response.status_code,
                url,
            )
            return None

        try:
            data = response.json()
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    def _analizar_repos(
        self, repos: list[dict], empresa: Empresa, org: str
    ) -> list[Trigger]:
        if not repos:
            return []

        repos_con_match: list[dict] = []
        repos_activos: list[dict] = []

        for repo in repos:
            if repo.get("archived") or repo.get("fork"):
                continue

            lenguaje = repo.get("language")
            tiene_match = _match_tecnologias(lenguaje, self._tecnologias)

            if tiene_match:
                repos_con_match.append(repo)
            elif lenguaje:
                repos_activos.append(repo)

        if not repos_con_match and not repos_activos:
            logger.debug("GitHub: sin repos relevantes para org '%s'.", org)
            return []

        # Nivel de confianza: MEDIA si hay match con el ICP, BAJA si hay repos pero sin match
        if repos_con_match:
            nivel = NivelConfianza.MEDIA
            repos_a_reportar = repos_con_match
        else:
            # Sin match no generamos trigger (ruido bajo)
            logger.debug("GitHub: repos sin match con ICP para org '%s'.", org)
            return []

        # Fecha del repo más reciente con match
        fecha_evento: datetime | None = None
        for repo in repos_a_reportar:
            fecha = _parsear_fecha_github(repo.get("pushed_at"))
            if fecha and (fecha_evento is None or fecha > fecha_evento):
                fecha_evento = fecha

        # Construir descripción
        nombres_repos = [r.get("name", "?") for r in repos_a_reportar[:3]]
        lenguajes = list(
            {r.get("language", "?") for r in repos_a_reportar if r.get("language")}
        )
        issues_total = sum(r.get("open_issues_count", 0) for r in repos_a_reportar)

        descripcion = (
            f"Org GitHub '{org}' — {len(repos_con_match)} repo(s) activo(s) con match ICP. "
            f"Repos: {', '.join(nombres_repos)}. "
            f"Lenguajes: {', '.join(lenguajes)}. "
            f"Issues abiertos: {issues_total}."
        )

        logger.info(
            "GitHub: Trigger generado para '%s' — %d repos match, confianza %s",
            empresa.nombre,
            len(repos_con_match),
            nivel.value,
        )

        return [
            Trigger(
                empresa_id=empresa.id,
                origen=OrigenTrigger.GITHUB,
                nivel_confianza=nivel,
                descripcion=descripcion,
                fecha_evento=fecha_evento,
            )
        ]
