"""
ApolloDiscoveryAdapter — implementación de PuertoDescubridorEmpresas usando
la API de Apollo.io para descubrir empresas por FIRMOGRAFÍA PURA.

Rol en el pipeline (refactorización M1/M2, Hallazgo 2 de la corrida real):
    Es el ÚNICO descubridor del Motor 1. Encuentra el TAM base a partir del
    ManifiestoICP (sector/tamaño/país), SIN depender de si la empresa tiene
    señales activas (vacantes, contratos) en este momento — esa validación de
    señales es trabajo posterior del Motor 2 (TheirStack, SECOP, etc.). La
    versión anterior descubría con TheirStack, lo que sesgaba el TAM inicial
    solo a empresas que ya estaban contratando (colapsaba discovery con scoring).

Patrón HTTP: idéntico a src/adapters/enrichment/apollo_client.py — header
X-Api-Key, POST JSON, timeout, y NUNCA propagar excepción hacia el Core
(cualquier error → [] con log). El mapeo de tamaño replica la lógica de
_inferir_tamano de theirstack_adapter.py para mantener un único criterio de
firmografía en todo el Motor 2.

⚠️  NOTA IMPORTANTE (validación pendiente con clave real):
    NO existe hoy ningún test que fije el esquema EXACTO de request/response
    de la búsqueda de organizaciones de Apollo. Los nombres de endpoint, de
    parámetros de filtro (organization_num_employees_ranges,
    organization_locations) y de campos de respuesta (organizations/accounts,
    primary_domain, estimated_num_employees, country) se implementan de forma
    DEFENSIVA según la documentación pública de Apollo y el patrón de
    apollo_client.py. Deben confirmarse con una corrida real (smoke test) con
    APOLLO_API_KEY antes de darse por definitivos. El adaptador está escrito
    para degradar a [] (nunca romper) si el esquema real difiere.
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

# Endpoint de búsqueda de organizaciones de Apollo. mixed_companies/search es
# el usado para descubrir cuentas por firmografía; se deja documentado el
# alterno /v1/organizations/search por si el esquema real difiere.
_SEARCH_ENDPOINT = "https://api.apollo.io/api/v1/mixed_companies/search"
_REQUEST_TIMEOUT_SECS = 15

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

# Mapeo ISO Alpha-2 → nombre de país que Apollo espera en
# organization_locations. Defensivo y parcial: si el código no está aquí, se
# pasa el valor crudo del ICP (Apollo tolera nombres y algunos códigos). Debe
# validarse contra el comportamiento real de la API con clave.
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
    # Quitar esquema
    for prefijo in ("https://", "http://"):
        if website.startswith(prefijo):
            website = website[len(prefijo):]
            break
    if website.startswith("www."):
        website = website[4:]
    # Quitar path/query
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
        Descubre empresas candidatas por firmografía pura (sector/tamaño/país
        del ICP) vía la búsqueda de organizaciones de Apollo.

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
        ManifiestoICP. Solo agrega filtros cuando el dato existe en el ICP
        (filtros ausentes = búsqueda más amplia, no un error).
        """
        payload: dict = {"per_page": self._max_empresas}

        rangos = _RANGOS_EMPLEADOS_POR_TAMANO.get(manifesto.tamano_empresa)
        if rangos:
            payload["organization_num_employees_ranges"] = rangos

        geografia = (manifesto.geografia or "").strip()
        if geografia and geografia.upper() != "LATAM":
            ubicacion = _NOMBRE_PAIS_POR_ISO.get(geografia.upper(), geografia)
            payload["organization_locations"] = [ubicacion]

        return payload

    def _parsear_empresas(
        self, data: dict, manifesto: ManifiestoICP
    ) -> list[Empresa]:
        """
        Convierte la respuesta de Apollo en objetos Empresa(estado=DESCUBIERTA).
        Deduplica por dominio; omite entradas sin dominio o sin nombre.
        """
        organizaciones = data.get("organizations")
        if not organizaciones:
            organizaciones = data.get("accounts", [])

        dominios_vistos: set[str] = set()
        empresas: list[Empresa] = []

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

            if dominio in dominios_vistos:
                continue
            dominios_vistos.add(dominio)

            tamano = _inferir_tamano(org.get("estimated_num_employees"))

            # NUNCA asumir 'CO' ante país ausente (bug caso Parcero/UK). Usar
            # el centinela PAIS_DESCONOCIDO, que PoliticaValidacionGeografica
            # trata como no verificable.
            pais_raw = org.get("country") or org.get("country_code")
            pais = pais_raw.strip().upper()[:2] if pais_raw else PAIS_DESCONOCIDO

            empresa = Empresa(
                nombre=nombre,
                dominio=dominio,
                tamano=tamano,
                vertical=manifesto.vertical,
                pais=pais,
                estado=EstadoEmpresa.DESCUBIERTA,
            )
            empresas.append(empresa)

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
        """
        try:
            logger.info(
                "Apollo Discovery: buscando organizaciones (per_page=%d)",
                self._max_empresas,
            )
            response = requests.post(
                _SEARCH_ENDPOINT,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Cache-Control": "no-cache",
                    "X-Api-Key": self._api_key,
                },
                timeout=_REQUEST_TIMEOUT_SECS,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.warning("Apollo Discovery: timeout. Retornando [].")
            return None
        except requests.exceptions.HTTPError as exc:
            logger.warning(
                "Apollo Discovery: HTTP %s. Retornando [].",
                exc.response.status_code if exc.response is not None else "?",
            )
            return None
        except requests.exceptions.RequestException as exc:
            logger.error("Apollo Discovery: error de red: %s", exc)
            return None
        except Exception as exc:  # noqa: BLE001 — contrato: nunca propagar al Core
            logger.error("Apollo Discovery: error inesperado: %s", exc)
            return None
