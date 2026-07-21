"""
PaqueteRevisionAdapter — persistencia de la cola de revisión manual accionable.

Diseño: respuesta directa al rechazo del usuario a la propuesta anterior de
"cola con solo un estado PERMITIDO/EXCLUIDO/PENDIENTE" — un estado sin
evidencia no le da al humano nada con qué decidir, solo lo obliga a
re-investigar desde cero. Este adaptador persiste, por empresa pendiente, un
"Paquete de Revisión": toda la evidencia que el pipeline YA leyó (snippet de
homepage, motivo exacto de indeterminación) más links de un clic hacia las
fuentes públicas donde un humano puede confirmar la decisión en minutos
(Google, LinkedIn, RUES búsqueda avanzada, y el `urlproceso` de SECOP si hay
un Trigger de contrato ganado).

Formato de persistencia: JSON plano (`revision_manual/pendientes.json`) — el
pipeline aún está en fase de backend puro (sin dashboard ni base de datos),
así que un archivo humano-legible y versionable es la opción correcta hoy;
migrar a una tabla real cuando exista el dashboard es un cambio de adaptador,
no de Core (el Core nunca importa este módulo).

Ciclo de vida de un registro:
    1. El orquestador (sandbox_tbbc_real.py) detecta PENDIENTE_REVISION_MANUAL
       o INDETERMINADO y llama a `registrar_pendiente()`.
    2. Si la empresa YA tiene una decisión humana persistida
       (estado_revision != PENDIENTE), el orquestador debe RESPETARLA — no
       volver a gastar Capa 2 en ella. Ver `obtener_decision_humana()`.
    3. Si sigue PENDIENTE, el orquestador reintenta automáticamente la Capa 2
       (muchos "indeterminados" son fallas transitorias, no ambigüedad real)
       ANTES de volver a mostrarla al humano.
    4. El humano edita el archivo a mano, cambiando `estado_revision` a
       CONFIRMADO_PERMITIDO o CONFIRMADO_EXCLUIDO.

Contrato de error: operaciones de disco (I/O) SÍ pueden fallar (permisos,
disco lleno, JSON corrupto por edición manual). A diferencia del resto de
adaptadores del proyecto (que nunca propagan al Core porque hablan con APIs
externas no confiables), este adaptador trata el archivo local como una
dependencia confiable — un fallo de persistencia es un problema real de
configuración del entorno que el operador debe ver, no silenciar. Se loguea
como error y se propaga la excepción de I/O original.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from urllib.parse import quote_plus

from src.core.domain.models import Empresa, Trigger

logger = logging.getLogger(__name__)

_RUTA_DEFAULT = Path("revision_manual") / "pendientes.json"


class EstadoRevisionHumana(str, Enum):
    """
    Estado de la decisión humana sobre un Paquete de Revisión.

    PENDIENTE              → aún sin decisión humana. El orquestador debe
                              reintentar la Capa 2 automáticamente antes de
                              volver a mostrarlo (muchos PENDIENTE son fallas
                              transitorias, no ambigüedad real).
    CONFIRMADO_PERMITIDO   → el humano revisó la evidencia y confirmó que la
                              empresa NO es competidor / SÍ es geografía
                              válida. El orquestador debe tratarla como
                              PERMITIDO en corridas futuras sin re-consultar
                              la Capa 2.
    CONFIRMADO_EXCLUIDO    → el humano revisó y confirmó exclusión (es
                              competidor real o geografía inválida). El
                              orquestador debe descartarla en corridas
                              futuras sin re-consultar la Capa 2.
    """

    PENDIENTE = "PENDIENTE"
    CONFIRMADO_PERMITIDO = "CONFIRMADO_PERMITIDO"
    CONFIRMADO_EXCLUIDO = "CONFIRMADO_EXCLUIDO"


@dataclass(frozen=True)
class LinksVerificacion:
    """Links de un clic hacia fuentes públicas para verificación humana rápida."""

    google: str
    linkedin: str
    rues_busqueda_avanzada: str
    secop_urlproceso: str | None = None


@dataclass(frozen=True)
class PaqueteRevision:
    """
    Un registro de la cola de revisión manual: toda la evidencia disponible
    sobre UNA empresa pendiente, más los links de verificación.
    """

    empresa_id: str
    empresa_nombre: str
    empresa_dominio: str
    motivo: str
    snippet_homepage: str | None
    links: LinksVerificacion
    estado_revision: EstadoRevisionHumana
    fecha_registro: str
    fecha_ultima_actualizacion: str
    nota_humana: str | None = None


def _construir_links(empresa: Empresa, triggers: list[Trigger] | None) -> LinksVerificacion:
    """
    Construye los links de un clic. `triggers` es opcional — si viene una
    lista con un Trigger de SECOP cuya descripción incluye una URL de
    proceso, se extrae para dar acceso directo al contrato público.
    """
    nombre_q = quote_plus(empresa.nombre)
    nit_q = quote_plus(empresa.nit_o_tax_id) if empresa.nit_o_tax_id else nombre_q

    secop_url: str | None = None
    if triggers:
        for t in triggers:
            if "URL: http" in t.descripcion:
                secop_url = t.descripcion.split("URL: ", 1)[1].strip()
                break

    return LinksVerificacion(
        google=f"https://www.google.com/search?q={nombre_q}",
        linkedin=f"https://www.linkedin.com/search/results/companies/?keywords={nombre_q}",
        rues_busqueda_avanzada=f"https://ruesfront.rues.org.co/busqueda-avanzada?q={nit_q}",
        secop_urlproceso=secop_url,
    )


class PaqueteRevisionAdapter:
    """
    Persiste y consulta la cola de revisión manual en un archivo JSON local.

    Args:
        ruta_archivo: Ruta del JSON de persistencia. Por defecto
                      'revision_manual/pendientes.json' relativo al cwd del
                      proceso (mismo patrón que el resto de scripts del
                      sandbox, que asumen ejecución desde la raíz del repo).
    """

    def __init__(self, ruta_archivo: Path | str | None = None) -> None:
        self._ruta = Path(ruta_archivo) if ruta_archivo else _RUTA_DEFAULT

    # ──────────────────────────────────────────────────────────────────────
    # Lectura
    # ──────────────────────────────────────────────────────────────────────
    def _cargar(self) -> dict[str, dict]:
        """
        Retorna el contenido crudo del archivo (dict empresa_id -> registro).
        Archivo inexistente → {} (primera corrida, estado válido, no error).
        JSON corrupto → se loguea como error y se propaga (fail-loud: un
        archivo corrupto por edición manual accidental no debe silenciarse,
        el operador necesita saberlo para no perder decisiones humanas).
        """
        if not self._ruta.exists():
            return {}
        try:
            with self._ruta.open("r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as exc:
            logger.error(
                "PaqueteRevisionAdapter: '%s' contiene JSON inválido: %s. "
                "Revisa el archivo manualmente antes de continuar.",
                self._ruta,
                exc,
            )
            raise

    def _guardar(self, datos: dict[str, dict]) -> None:
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        with self._ruta.open("w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2, sort_keys=True)

    def obtener_decision_humana(self, empresa_id: str) -> EstadoRevisionHumana | None:
        """
        Retorna el EstadoRevisionHumana persistido para esta empresa, o None
        si nunca se registró (nunca pasó por revisión manual). El
        orquestador debe llamar esto ANTES de re-evaluar Capa 2 en cada
        corrida — si ya hay una decisión humana, se respeta sin gastar LLM.
        """
        datos = self._cargar()
        registro = datos.get(str(empresa_id))
        if registro is None:
            return None
        return EstadoRevisionHumana(registro["estado_revision"])

    def listar_pendientes(self) -> list[PaqueteRevision]:
        """Retorna todos los registros con estado_revision == PENDIENTE."""
        datos = self._cargar()
        pendientes = []
        for registro in datos.values():
            if registro["estado_revision"] == EstadoRevisionHumana.PENDIENTE.value:
                pendientes.append(_registro_a_paquete(registro))
        return pendientes

    # ──────────────────────────────────────────────────────────────────────
    # Escritura
    # ──────────────────────────────────────────────────────────────────────
    def registrar_pendiente(
        self,
        empresa: Empresa,
        motivo: str,
        snippet_homepage: str | None = None,
        triggers: list[Trigger] | None = None,
    ) -> PaqueteRevision:
        """
        Registra (o re-registra, si ya existía y seguía PENDIENTE) un
        Paquete de Revisión para la empresa dada.

        Si la empresa YA tiene una decisión humana (CONFIRMADO_*), este
        método NO la sobrescribe — retorna el registro existente intacto.
        Esto protege ediciones manuales de ser pisadas por una corrida
        automática posterior. Para forzar un nuevo ciclo de revisión sobre
        una empresa ya decidida, el humano debe editar el JSON directamente
        (cambiar estado_revision a PENDIENTE).
        """
        datos = self._cargar()
        clave = str(empresa.id)
        ahora = datetime.now(timezone.utc).isoformat()

        existente = datos.get(clave)
        if existente is not None and existente["estado_revision"] != EstadoRevisionHumana.PENDIENTE.value:
            logger.info(
                "PaqueteRevisionAdapter: '%s' ya tiene decisión humana (%s). "
                "No se sobrescribe.",
                empresa.nombre,
                existente["estado_revision"],
            )
            return _registro_a_paquete(existente)

        links = _construir_links(empresa, triggers)
        registro = {
            "empresa_id": clave,
            "empresa_nombre": empresa.nombre,
            "empresa_dominio": empresa.dominio,
            "motivo": motivo,
            "snippet_homepage": snippet_homepage,
            "links": {
                "google": links.google,
                "linkedin": links.linkedin,
                "rues_busqueda_avanzada": links.rues_busqueda_avanzada,
                "secop_urlproceso": links.secop_urlproceso,
            },
            "estado_revision": EstadoRevisionHumana.PENDIENTE.value,
            "fecha_registro": existente["fecha_registro"] if existente else ahora,
            "fecha_ultima_actualizacion": ahora,
            "nota_humana": existente.get("nota_humana") if existente else None,
        }
        datos[clave] = registro
        self._guardar(datos)

        logger.info(
            "PaqueteRevisionAdapter: '%s' registrada en cola de revisión manual.",
            empresa.nombre,
        )
        return _registro_a_paquete(registro)

    def marcar_decision(
        self,
        empresa_id: str,
        estado: EstadoRevisionHumana,
        nota_humana: str | None = None,
    ) -> None:
        """
        API programática equivalente a la edición manual del JSON — útil
        para tests y para una futura UI/CLI de revisión. Lanza KeyError si
        la empresa no está registrada.
        """
        datos = self._cargar()
        clave = str(empresa_id)
        if clave not in datos:
            raise KeyError(f"Empresa '{empresa_id}' no está en la cola de revisión.")

        datos[clave]["estado_revision"] = estado.value
        datos[clave]["fecha_ultima_actualizacion"] = datetime.now(timezone.utc).isoformat()
        if nota_humana is not None:
            datos[clave]["nota_humana"] = nota_humana
        self._guardar(datos)


def _registro_a_paquete(registro: dict) -> PaqueteRevision:
    links_raw = registro["links"]
    return PaqueteRevision(
        empresa_id=registro["empresa_id"],
        empresa_nombre=registro["empresa_nombre"],
        empresa_dominio=registro["empresa_dominio"],
        motivo=registro["motivo"],
        snippet_homepage=registro.get("snippet_homepage"),
        links=LinksVerificacion(
            google=links_raw["google"],
            linkedin=links_raw["linkedin"],
            rues_busqueda_avanzada=links_raw["rues_busqueda_avanzada"],
            secop_urlproceso=links_raw.get("secop_urlproceso"),
        ),
        estado_revision=EstadoRevisionHumana(registro["estado_revision"]),
        fecha_registro=registro["fecha_registro"],
        fecha_ultima_actualizacion=registro["fecha_ultima_actualizacion"],
        nota_humana=registro.get("nota_humana"),
    )
