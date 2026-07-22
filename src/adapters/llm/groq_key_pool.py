"""
GroqKeyPool — pool de claves de API de Groq con rotación reactiva por cooldown.

Problema que resuelve (hallazgo de corrida real, 2026-07): el tier gratuito
de Groq impone un límite de Tokens Por Día (TPD) POR CLAVE. En un batch grande
del Motor 2, el mayor consumidor (PropuestaValorAdapter: una llamada LLM por
empresa candidata ambigua) agota una sola clave a mitad de camino y todo el
resto del lote falla con 429.

Diseño: rotación REACTIVA con AFINIDAD (no round-robin ciego). Se usa una sola
clave hasta que da 429; en ese momento se marca en enfriamiento (cooldown) por
el tiempo que el propio mensaje de error de Groq indica ("try again in Ns") y
se salta a la siguiente clave disponible. Una clave vuelve a estar disponible
cuando su cooldown expira. Los clientes `groq.Groq` se construyen de forma
perezosa y se cachean por clave (nunca se reconstruye el mismo cliente).

Este módulo ES un adaptador (capa externa), por lo que SÍ puede importar `groq`.
Contrato de error: ningún método lanza excepción hacia el llamador.
"""

from __future__ import annotations

import logging
import os
import re
import time

import groq

logger = logging.getLogger(__name__)

# Cuántas variables GROQ_API_KEY_N escanear del entorno cuando no se pasan
# claves explícitas.
_MAX_CLAVES_ENTORNO = 20

# Cooldown por defecto (segundos) cuando el mensaje de error de Groq no trae
# un "try again in Ns" parseable.
_COOLDOWN_DEFAULT_SECS = 60.0

# Extrae los segundos sugeridos del mensaje de rate limit de Groq
# (ej. "Please try again in 5.2s").
_PATRON_SEGUNDOS = re.compile(r"try again in ([\d.]+)s", re.IGNORECASE)


class GroqKeyPool:
    """
    Args:
        api_keys: Lista explícita de claves. Si se provee (incluso con una
            sola clave), se usa tal cual — solo se filtran las cadenas
            vacías. Si es None, se descubren del entorno (ver _descubrir_del_entorno).
    """

    def __init__(self, api_keys: list[str] | None = None) -> None:
        if api_keys is not None:
            claves = [k for k in api_keys if k]
        else:
            claves = self._descubrir_del_entorno()

        self._api_keys: list[str] = claves
        # Índice de la clave actualmente activa. Por defecto 0, incluso antes
        # de la primera llamada a cliente_activo() — así registrar_rate_limit()
        # sabe a qué clave penalizar si se llama "en frío".
        self._idx: int = 0
        # Cache de clientes construidos, por índice de clave (nunca se
        # reconstruye el mismo cliente).
        self._clients: dict[int, groq.Groq] = {}
        # Momento (time.monotonic) hasta el cual cada clave está en cooldown.
        self._cooldown_until: dict[int, float] = {}

    # ──────────────────────────────────────────────────────────────────────
    # Descubrimiento de claves del entorno
    # ──────────────────────────────────────────────────────────────────────
    @staticmethod
    def _descubrir_del_entorno() -> list[str]:
        """
        Descubre claves en este orden:
            1. GROQ_API_KEY_1, GROQ_API_KEY_2, ... (escanea 1.._MAX y para en
               el primer hueco — soporta la configuración multi-clave).
            2. Si no hay ninguna GROQ_API_KEY_N, usa [GROQ_API_KEY] si existe.
            3. Si nada está definido, lista vacía.
        """
        claves: list[str] = []
        for i in range(1, _MAX_CLAVES_ENTORNO + 1):
            valor = os.getenv(f"GROQ_API_KEY_{i}")
            if not valor:
                break  # primer hueco: detener el escaneo
            claves.append(valor)

        if claves:
            return claves

        unica = os.getenv("GROQ_API_KEY")
        if unica:
            return [unica]
        return []

    # ──────────────────────────────────────────────────────────────────────
    # Propiedades
    # ──────────────────────────────────────────────────────────────────────
    @property
    def tiene_claves(self) -> bool:
        return len(self._api_keys) >= 1

    @property
    def num_claves(self) -> int:
        return len(self._api_keys)

    # ──────────────────────────────────────────────────────────────────────
    # Selección de cliente activo
    # ──────────────────────────────────────────────────────────────────────
    def cliente_activo(self) -> "groq.Groq | None":
        """
        Retorna el cliente Groq de la PRIMERA clave sin cooldown activo
        (escaneando desde el índice 0), construyéndolo perezosamente y
        cacheándolo por clave. Fija self._idx a la clave elegida.

        Si todas las claves están en cooldown, o no hay claves, retorna None.
        Nunca lanza excepción.
        """
        ahora = time.monotonic()
        for i, api_key in enumerate(self._api_keys):
            if ahora >= self._cooldown_until.get(i, 0.0):
                self._idx = i
                cliente = self._clients.get(i)
                if cliente is None:
                    try:
                        cliente = groq.Groq(api_key=api_key)
                    except Exception as exc:  # noqa: BLE001 — nunca propagar
                        logger.error(
                            "GroqKeyPool: fallo construyendo cliente para la "
                            "clave índice %d: %s",
                            i,
                            exc,
                        )
                        return None
                    self._clients[i] = cliente
                return cliente
        return None

    # ──────────────────────────────────────────────────────────────────────
    # Registro de rate limit (failover)
    # ──────────────────────────────────────────────────────────────────────
    def registrar_rate_limit(self, exc) -> "groq.Groq | None":
        """
        Marca la clave actualmente activa (self._api_keys[self._idx]) en
        cooldown por los segundos parseados del mensaje del error (o
        _COOLDOWN_DEFAULT_SECS si no parsea), y retorna la siguiente clave
        disponible vía cliente_activo() (o None si el pool quedó agotado).

        NO construye ningún cliente para la clave penalizada. Si se llama
        antes de cualquier cliente_activo(), penaliza la clave índice 0 (el
        valor por defecto de self._idx). Nunca lanza excepción.
        """
        try:
            if not self._api_keys:
                return None
            segundos = self._parsear_segundos(exc)
            self._cooldown_until[self._idx] = time.monotonic() + segundos
            logger.warning(
                "GroqKeyPool: clave índice %d en cooldown por %.1fs.",
                self._idx,
                segundos,
            )
            return self.cliente_activo()
        except Exception as exc_interno:  # noqa: BLE001 — nunca propagar
            logger.error(
                "GroqKeyPool: error inesperado en registrar_rate_limit: %s",
                exc_interno,
            )
            return None

    @staticmethod
    def _parsear_segundos(exc) -> float:
        """Extrae los segundos de 'try again in Ns' del error; default 60s."""
        try:
            match = _PATRON_SEGUNDOS.search(str(exc))
            if match:
                return float(match.group(1))
        except (ValueError, TypeError):
            pass
        return _COOLDOWN_DEFAULT_SECS
