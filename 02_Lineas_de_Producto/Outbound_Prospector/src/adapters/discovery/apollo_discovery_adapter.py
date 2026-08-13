"""
ApolloDiscoveryAdapter — implementación de PuertoDescubridorEmpresas usando
la API de Apollo.io para descubrir empresas del SECTOR TECNOLOGÍA acordes al ICP.

Rol en el pipeline (refactorización M1/M2, Hallazgo 2 de la corrida real):
    Es el ÚNICO descubridor del Motor 1. Encuentra el TAM base a partir del
    ManifiestoICP (sector/tecnología/tamaño/país), SIN depender de si la empresa
    tiene señales activas (vacantes, contratos) en este momento — esa validación
    de señales es trabajo posterior del Motor 2 (TheirStack, SECOP, etc.).

FIX (defecto de filtrado — corrida real: 44 empresas, ninguna tech):
    La versión anterior SOLO filtraba por tamaño (organization_num_employees_ranges)
    y país (organization_locations). Nunca por industria ni tecnología, así que
    devolvía ONGs, medios, gremios y entes públicos (elempleo, Forbes, Trabajo
    Humanitario...). Ahora el payload también deriva DEL ICP:
      - Filtro de TECNOLOGÍA (currently_using_any_of_technology_uids) desde
        manifesto.anclaje_tecnologico.
      - Filtro de INDUSTRIA/KEYWORDS (q_organization_keyword_tags) desde
        manifesto.industrias_objetivo (industrias COMPRADORAS derivadas del ICP
        por el LLM — NUNCA la categoría del propio cliente, que devolvería
        competidores; ese fue el defecto del run #2).

VALIDACIÓN EMPÍRICA (contra la API real, mixed_companies/search, per_page=5):
    - baseline (solo tamaño+país, Colombia): 6.176 resultados, 100% ruido no-tech.
    - + q_organization_keyword_tags=["software development","saas"]: 389 resultados,
      con empresas tech reales (BPT Software, Hunty, Imagine Apps — NAICS 541511
      "Custom Computer Programming", 513210 "Software Publishers").
    - + currently_using_any_of_technology_uids=[...]: HTTP 422
      "Cannot access advanced filters ... on free plan. Please start a trial or
      upgrade." → el filtro de tecnología (technographics) es un filtro AVANZADO
      de pago. Es el filtro correcto y más preciso (lo usará el plan de producción),
      pero en un plan free rompería toda la búsqueda.
    Conclusión de diseño: se envían AMBOS filtros; si el plan actual no permite el
    filtro de tecnología (422), el adaptador DEGRADA con gracia — reintenta una vez
    solo con industria/keywords/tamaño/país — en vez de romper (contrato: error → []).
    Campo de industria en la respuesta: `industry` (plan de pago) o `naics_codes`
    (disponible incluso en free) — se loggea para trazabilidad.

Patrón HTTP: idéntico a src/adapters/enrichment/apollo_client.py — header
X-Api-Key, POST JSON, timeout, y NUNCA propagar excepción hacia el Core.
El mapeo de tamaño replica _inferir_tamano de theirstack_adapter.py.
"""

from __future__ import annotations

import logging
import os

import requests

from src.core.domain.models import (
    PAIS_DESCONOCIDO,
    Empresa,
    EstadoEmpresa,
    ManifiestoICP,
    TamanoEmpresa,
)
from src.core.ports.interfaces import PuertoDescubridorEmpresas

logger = logging.getLogger(__name__)

# Endpoint de búsqueda de organizaciones de Apollo (docs oficiales:
# https://docs.apollo.io/reference/organization-search). Confirmado empíricamente.
_SEARCH_ENDPOINT = "https://api.apollo.io/api/v1/mixed_companies/search"
_REQUEST_TIMEOUT_SECS = 15

# Clave del filtro de tecnología de Apollo (technographics). Es un filtro
# AVANZADO (de pago): en planes free devuelve HTTP 422. Se aísla en constante
# para poder retirarlo del payload al degradar.
_TECH_FILTER_KEY = "currently_using_any_of_technology_uids"

# Mapeo TamanoEmpresa → rangos de empleados de Apollo
# (organization_num_employees_ranges). Los rangos usan el formato "min,max"
# documentado por Apollo. Cubren el mismo criterio ordinal que _inferir_tamano:
#   STARTUP < 50 ; SME 50–200 ; MID_MARKET 200–1000 ; ENTERPRISE > 1000.
_RANGOS_EMPLEADOS_POR_TAMANO: dict[TamanoEmpresa, list[str]] = {
    TamanoEmpresa.STARTUP: ["1,10", "11,20", "21,50"],
    TamanoEmpresa.SME: ["51,100", "101,200"],
    TamanoEmpresa.MID_MARKET: ["201,500", "501,1000"],
    TamanoEmpresa.ENTERPRISE: ["1001,2000", "2001,5000", "5001,10000", "10001"],
}

# Traducción de frontera ISO Alpha-2 → nombre de país que Apollo espera en
# organization_locations (confirmado: "Colombia" filtra por HQ). Parcial: si el
# código no está aquí, se pasa el valor crudo del ICP.
_NOMBRE_PAIS_POR_ISO: dict[str, str] = {
    "CO": "Colombia",
    "MX": "Mexico",
    "AR": "Argentina",
    "CL": "Chile",
    "PE": "Peru",
    "BR": "Brazil",
    "US": "United States",
    "ES": "Spain",
}


def _traducir_tech_uid(nombre: str) -> str:
    """
    Traducción de FRONTERA del adaptador: nombre de tecnología del ICP → uid de
    Apollo. Regla oficial de Apollo (docs organization-search): usar guiones
    bajos para reemplazar espacios y puntos, en minúsculas. Ejemplos:
        "Amazon Web Services" → "amazon_web_services"
        "Google Analytics"    → "google_analytics"
        "Node.js"             → "node_js"
        "PostgreSQL"          → "postgresql"

    NO es una regla de negocio ni una tabla hardcodeada: es la misma clase de
    traducción sintáctica que TheirStackAdapter aplica con
    `t.lower().replace(" ", "-")`. Mínima, mecánica y documentada.
    """
    slug = nombre.strip().lower()
    for ch in (" ", ".", "/"):
        slug = slug.replace(ch, "_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_")


def _inferir_tamano(employee_count: int | None) -> TamanoEmpresa:
    """
    Mapea el número de empleados al Enum TamanoEmpresa. MISMA lógica que
    theirstack_adapter._inferir_tamano (criterio único de firmografía):
        < 50 → STARTUP ; 50–200 → SME ; 201–1000 → MID_MARKET ; > 1000 → ENTERPRISE.
    Ante dato ausente/no positivo, SME como valor seguro por defecto (una
    Empresa descubierta DEBE nacer con algún tamaño).
    """
    if not employee_count or employee_count <= 0:
        return TamanoEmpresa.SME
    if employee_count < 50:
        return TamanoEmpresa.STARTUP
    if employee_count <= 200:
        return TamanoEmpresa.SME
    if employee_count <= 1000:
        return TamanoEmpresa.MID_MARKET
    return TamanoEmpresa.ENTERPRISE


def _derivar_dominio(org: dict) -> str:
    """
    Extrae el dominio de una organización de Apollo. Prioriza primary_domain;
    si no está, deriva de website_url quitando protocolo, 'www.' y path.
    Retorna cadena vacía si no hay ninguno (el llamador omite la entrada).
    """
    dominio = (org.get("primary_domain") or "").strip().lower()
    if dominio:
        return dominio

    website = (org.get("website_url") or "").strip().lower()
    if not website:
        return ""
    for prefijo in ("https://", "http://"):
        if website.startswith(prefijo):
            website = website[len(prefijo) :]
            break
    if website.startswith("www."):
        website = website[4:]
    website = website.split("/")[0].split("?")[0]
    return website.strip()


class ApolloDiscoveryAdapter(PuertoDescubridorEmpresas):
    """
    Args:
        api_key: Clave de API de Apollo. Si None, lee de APOLLO_API_KEY.
        max_empresas_discovery: Máximo de organizaciones a solicitar por
            llamada (per_page de Apollo).
    """

    def __init__(
        self,
        api_key: str | None = None,
        max_empresas_discovery: int = 25,
    ) -> None:
        self._api_key = api_key or os.getenv("APOLLO_API_KEY")
        self._max_empresas = max_empresas_discovery
        if not self._api_key:
            logger.warning(
                "APOLLO_API_KEY no configurada. "
                "ApolloDiscoveryAdapter retornará listas vacías hasta que se configure."
            )

    def descubrir_empresas(self, manifesto: ManifiestoICP) -> list[Empresa]:
        """
        Descubre empresas candidatas del sector tecnología (tecnología/industria/
        tamaño/país del ICP) vía la búsqueda de organizaciones de Apollo.

        Implementa PuertoDescubridorEmpresas.descubrir_empresas().
        Contrato: nunca lanza excepción. Sin api_key o ante cualquier error → [].
        """
        if not self._api_key:
            return []

        payload = self._construir_payload(manifesto)
        data = self._llamar_api(payload)
        if data is None:
            return []

        return self._parsear_empresas(data, manifesto)

    def _construir_payload(self, manifesto: ManifiestoICP) -> dict:
        """
        Construye el cuerpo de la búsqueda de organizaciones a partir del
        ManifiestoICP. Solo agrega un filtro cuando el dato existe en el ICP
        (filtro ausente = búsqueda más amplia, no un error).

        Cada filtro se DERIVA del ICP (nada hardcodeado de negocio):
          - tamaño   ← manifesto.tamano_empresa   (organization_num_employees_ranges)
          - país     ← manifesto.geografia         (organization_locations)
          - tecnología ← manifesto.anclaje_tecnologico (currently_using_any_of_technology_uids)
          - industria/keywords ← manifesto.industrias_objetivo (industrias
                                  compradoras derivadas del ICP; q_organization_keyword_tags)
        """
        payload: dict = {"per_page": self._max_empresas}

        # --- Tamaño (firmografía) ---
        rangos = _RANGOS_EMPLEADOS_POR_TAMANO.get(manifesto.tamano_empresa)
        if rangos:
            payload["organization_num_employees_ranges"] = rangos

        # --- País (HQ) ---
        geografia = (manifesto.geografia or "").strip()
        if geografia and geografia.upper() != "LATAM":
            ubicacion = _NOMBRE_PAIS_POR_ISO.get(geografia.upper(), geografia)
            payload["organization_locations"] = [ubicacion]

        # --- Tecnología (technographics) derivada de anclaje_tecnologico ---
        # Traducción de frontera nombre→uid. Filtro AVANZADO de Apollo: si el
        # plan no lo permite (422), _llamar_api degrada retirándolo.
        tech_uids = self._derivar_tech_uids(manifesto.anclaje_tecnologico)
        if tech_uids:
            payload[_TECH_FILTER_KEY] = tech_uids

        # --- Industria / keywords derivada de vertical + categoria_empresa ---
        # Texto libre (q_organization_keyword_tags): confirmado empíricamente que
        # filtra al sector tecnología en el plan actual. Es la vía derivable del
        # ICP sin tabla de IDs internos de industria.
        keyword_tags = self._derivar_keyword_tags(manifesto)
        if keyword_tags:
            payload["q_organization_keyword_tags"] = keyword_tags

        # --- Liderazgo y Personas ---
        # Pivot SHiFT! Motor 1: buscar CTOs / VPs de ingeniería
        payload["person_titles"] = ["CTO", "CIO", "VP of Engineering", "Chief Technology Officer"]
        
        return payload

    @staticmethod
    def _derivar_tech_uids(anclaje_tecnologico: list[str] | None) -> list[str]:
        """
        Deriva la lista de uids de tecnología de Apollo desde
        manifesto.anclaje_tecnologico (traducción de frontera, ver
        _traducir_tech_uid). Deduplica preservando el orden.
        """
        uids: list[str] = []
        for nombre in anclaje_tecnologico or []:
            uid = _traducir_tech_uid(nombre)
            if uid and uid not in uids:
                uids.append(uid)
        return uids

    @staticmethod
    def _derivar_keyword_tags(manifesto: ManifiestoICP) -> list[str]:
        """
        Deriva los keyword tags de industria desde manifesto.industrias_objetivo:
        las industrias COMPRADORAS que el LLM del Motor 1 infirió del ICP (los
        sectores que comprarían los servicios del cliente).

        CAMBIO 24-jul-2026 (path A, sin hardcode): antes se derivaba de
        manifesto.vertical + manifesto.categoria_empresa. Ese era el defecto de
        raíz del run #2 — categoria_empresa es la categoría del PROPIO CLIENTE,
        así que buscar por ella devolvía COMPETIDORES (otras consultoras/fábricas
        de software). Ahora se usan exclusivamente las industrias compradoras
        derivadas del ICP. La exclusión de competidores NO se hace aquí: es
        responsabilidad del Negative ICP semántico del Motor 2 (única fuente).

        Normaliza a minúsculas y deduplica preservando el orden. Lista vacía si
        el ICP no definió industrias objetivo → Apollo busca solo por
        tecnología+tamaño+país (más amplio, pero sin sesgo hacia competidores).
        """
        tags: list[str] = []
        for industria in manifesto.industrias_objetivo or []:
            tag = industria.strip().lower()
            if tag and tag not in tags:
                tags.append(tag)
        return tags

    def _parsear_empresas(self, data: dict, manifesto: ManifiestoICP) -> list[Empresa]:
        """
        Convierte la respuesta de Apollo en objetos Empresa(estado=DESCUBIERTA).
        Deduplica por dominio; omite entradas sin dominio o sin nombre.
        Loggea la industria de cada org (campo `industry` en planes de pago;
        `naics_codes` como respaldo) para trazabilidad del filtrado.
        """
        organizaciones = data.get("organizations")
        if not organizaciones:
            organizaciones = data.get("accounts", [])

        dominios_vistos: set[str] = set()
        empresas: list[Empresa] = []
        
        cont_excluidas = 0

        for org in organizaciones:
            if not isinstance(org, dict):
                continue

            nombre = (org.get("name") or "").strip()
            dominio = _derivar_dominio(org)
            if not nombre or not dominio:
                logger.debug(
                    "Apollo Discovery: organización sin nombre/dominio, omitida."
                )
                continue

            # FILTRO DURO ANTI-BASURA (Educación, Gobierno, ONGs)
            # Como la API gratuita de Apollo puede no soportar exclusiones avanzadas,
            # filtramos en memoria por nombre e industria.
            nombre_lower = nombre.lower()
            industria_raw = org.get("industry") or org.get("naics_codes") or ""
            if isinstance(industria_raw, list):
                industria_lower = " ".join(str(i) for i in industria_raw).lower()
            else:
                industria_lower = str(industria_raw).lower()
            texto_evaluacion = f"{nombre_lower} {industria_lower}"
            
            exclusiones = [
                "universidad", "colegio", "school", "education", "educacion", "educación",
                "gobierno", "government", "ministerio", "alcaldia", "alcaldía", "secretaria",
                "fundacion", "fundación", "ong", "non-profit", "non profit", "hospital",
                "clinica", "clínica",
                "magneto", "computrabajo", "headhunter", "staffing", "reclutamiento", "recruiting", "talent"
            ]
            if any(exc in texto_evaluacion for exc in exclusiones):
                logger.debug(
                    "Apollo Discovery: '%s' descartada por filtro duro anti-basura.",
                    nombre
                )
                cont_excluidas += 1
                continue

            if dominio in dominios_vistos:
                continue
            dominios_vistos.add(dominio)

            tamano = _inferir_tamano(org.get("estimated_num_employees"))

            # NUNCA asumir 'CO' ante país ausente (bug caso Parcero/UK). Usar
            # el centinela PAIS_DESCONOCIDO, que PoliticaValidacionGeografica
            # trata como no verificable.
            pais_raw = org.get("country") or org.get("country_code")
            pais = pais_raw.strip().upper()[:2] if pais_raw else PAIS_DESCONOCIDO

            # Trazabilidad del filtrado por industria.
            industria = org.get("industry") or org.get("naics_codes") or "desconocida"
            logger.info(
                "Apollo Discovery: '%s' (%s) — industria/naics=%s",
                nombre,
                dominio,
                industria,
            )

            empresa = Empresa(
                nombre=nombre,
                dominio=dominio,
                tamano=tamano,
                vertical=manifesto.vertical,
                pais=pais,
                estado=EstadoEmpresa.DESCUBIERTA,
            )
            empresas.append(empresa)

        if cont_excluidas > 0:
            logger.debug("Descartada por filtro anti-basura: %d de %d procesadas", cont_excluidas, len(organizaciones))

        logger.info(
            "Apollo Discovery: %d empresa(s) únicas descubiertas para ICP '%s'.",
            len(empresas),
            manifesto.categoria_empresa.value,
        )
        return empresas

    def _llamar_api(self, payload: dict) -> dict | None:
        """
        POST a Apollo con el mismo patrón que ApolloClient (header X-Api-Key,
        timeout). Contrato: nunca propaga al Core; retorna None ante cualquier
        error.

        Degradación con gracia (validada empíricamente): si el plan actual no
        permite el filtro AVANZADO de tecnología, Apollo responde HTTP 422. En
        ese caso reintentamos UNA vez retirando `currently_using_any_of_technology_uids`
        y conservando industria/keywords/tamaño/país, en vez de romper la
        búsqueda. Así el filtro de tecnología se aprovecha en planes de pago y el
        de industria/keywords sigue funcionando en cualquier plan.
        """
        response = self._ejecutar_post(payload)
        if response is None:
            return None

        if (
            response.status_code == 422
            and _TECH_FILTER_KEY in payload
            and self._es_error_filtro_avanzado(response)
        ):
            logger.warning(
                "Apollo Discovery: el filtro de tecnología '%s' no está disponible "
                "en el plan actual (HTTP 422). Reintentando solo con industria/"
                "keywords/tamaño/país.",
                _TECH_FILTER_KEY,
            )
            payload_degradado = {
                clave: valor
                for clave, valor in payload.items()
                if clave != _TECH_FILTER_KEY
            }
            response = self._ejecutar_post(payload_degradado)
            if response is None:
                return None

        return self._procesar_respuesta(response)

    def _ejecutar_post(self, payload: dict) -> requests.Response | None:
        """
        Ejecuta el POST y devuelve la Response cruda (sin raise_for_status, para
        poder inspeccionar 422 antes de decidir degradar). Retorna None ante
        errores de red/timeout — nunca propaga al Core.
        """
        try:
            logger.info(
                "Apollo Discovery: buscando organizaciones (per_page=%d, filtros=%s)",
                self._max_empresas,
                sorted(k for k in payload if k != "per_page"),
            )
            return requests.post(
                _SEARCH_ENDPOINT,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Cache-Control": "no-cache",
                    "X-Api-Key": self._api_key,
                },
                timeout=_REQUEST_TIMEOUT_SECS,
            )
        except requests.exceptions.Timeout:
            logger.warning("Apollo Discovery: timeout. Retornando [].")
            return None
        except requests.exceptions.RequestException as exc:
            logger.error("Apollo Discovery: error de red: %s", exc)
            return None
        except Exception as exc:  # noqa: BLE001 — contrato: nunca propagar al Core
            logger.error("Apollo Discovery: error inesperado en POST: %s", exc)
            return None

    @staticmethod
    def _es_error_filtro_avanzado(response: requests.Response) -> bool:
        """
        Detecta el 422 específico de Apollo por usar un filtro avanzado no
        disponible en el plan. Se apoya en el texto del cuerpo (mensaje real:
        "Cannot access advanced filters ... on free plan. Please ... upgrade.").
        """
        try:
            cuerpo = (response.text or "").lower()
        except Exception:  # noqa: BLE001
            return False
        return (
            _TECH_FILTER_KEY in cuerpo
            or "advanced filter" in cuerpo
            or "upgrade" in cuerpo
        )

    def _procesar_respuesta(self, response: requests.Response) -> dict | None:
        """
        Valida el status final y parsea el JSON. Retorna None ante cualquier
        error (contrato: nunca propaga al Core).
        """
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError:
            logger.warning(
                "Apollo Discovery: HTTP %s. Retornando [].",
                response.status_code,
            )
            return None
        except Exception as exc:  # noqa: BLE001 — contrato: nunca propagar al Core
            logger.error("Apollo Discovery: error al parsear respuesta: %s", exc)
            return None
