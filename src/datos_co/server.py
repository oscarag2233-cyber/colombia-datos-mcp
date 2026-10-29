"""Servidor MCP. Transporte stdio (Claude Desktop / Claude Code) o HTTP (conector remoto para
Claude y ChatGPT). Todas las herramientas son de solo lectura."""

from __future__ import annotations

import argparse
import os

from fastmcp import FastMCP

from . import store
from .envelope import envelope, error
from .sources import ofac, rama_judicial, rues, secop

mcp = FastMCP(
    "colombia-datos",
    instructions=(
        "Datos públicos de Colombia con trazabilidad. Cada respuesta trae fuente, URL y fecha de consulta. "
        "No completes ni reconstruyas datos ausentes. Si verified_endpoint es false, indícalo al usuario. "
        "Los resultados son borradores técnicos sujetos a verificación del abogado responsable."
    ),
)

RO = {"readOnlyHint": True, "openWorldHint": True}


@mcp.tool(annotations=RO)
async def secop_buscar_contratos(
    texto: str = "",
    documento_proveedor: str = "",
    nit_entidad: str = "",
    departamento: str = "",
    desde: str = "",
    hasta: str = "",
    limite: int = 20,
    pagina: int = 1,
) -> dict:
    """Busca contratos estatales en SECOP II (datos.gov.co). Fechas en AAAA-MM-DD."""
    try:
        return await secop.buscar_contratos(texto, documento_proveedor, nit_entidad, departamento, desde, hasta, limite, pagina)
    except Exception as e:  # noqa: BLE001
        return error("SECOP II", str(e), hint="Ejecute secop_describir_dataset y valide los nombres de columna.")


@mcp.tool(annotations=RO)
async def secop_buscar_procesos(texto: str = "", nit_entidad: str = "", limite: int = 20, pagina: int = 1) -> dict:
    """Busca procesos de contratación (licitaciones, convocatorias) en SECOP II."""
    try:
        return await secop.buscar_procesos(texto, nit_entidad, limite, pagina)
    except Exception as e:  # noqa: BLE001
        return error("SECOP II procesos", str(e))


@mcp.tool(annotations=RO)
async def secop_describir_dataset(dataset: str = "secop2_contratos") -> dict:
    """Devuelve columnas y metadatos reales de un dataset de datos.gov.co (clave configurada o ID Socrata)."""
    try:
        return await secop.describir(dataset)
    except Exception as e:  # noqa: BLE001
        return error("datos.gov.co", str(e))


@mcp.tool(annotations=RO)
async def sanciones_ofac_cribar(nombre: str, umbral: int = 85, limite: int = 10) -> dict:
    """Criba un nombre contra la lista SDN de OFAC (con alias). Es un indicio, no una determinación."""
    try:
        return await ofac.screen(nombre, umbral, limite)
    except Exception as e:  # noqa: BLE001
        return error("OFAC", str(e))


@mcp.tool(annotations=RO)
async def empresas_buscar(nit: str = "", nombre: str = "", limite: int = 10) -> dict:
    """Busca datos básicos de una empresa en el extracto abierto del RUES (requiere DS_RUES_ABIERTO)."""
    try:
        return await rues.buscar_empresa(nit, nombre, limite)
    except Exception as e:  # noqa: BLE001
        return error("RUES abierto", str(e))


@mcp.tool(annotations=RO)
async def procesos_consultar_radicado(radicado: str, solo_activos: bool = False) -> dict:
    """Consulta un proceso judicial por radicado de 23 dígitos (consulta pública; API interna del portal)."""
    try:
        return await rama_judicial.consultar_radicado(radicado, solo_activos)
    except Exception as e:  # noqa: BLE001
        return error("Rama Judicial", str(e))


@mcp.tool(annotations=RO)
async def procesos_actuaciones(radicado: str, pagina: int = 1) -> dict:
    """Lista las actuaciones de un proceso judicial por radicado de 23 dígitos (consulta pública)."""
    try:
        return await rama_judicial.consultar_actuaciones(radicado, pagina)
    except Exception as e:  # noqa: BLE001
        return error("Rama Judicial", str(e))


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
def jurisprudencia_buscar_local(texto: str, tipo: str = "", limite: int = 10) -> dict:
    """Busca en el índice local de jurisprudencia y normas cargadas por el titular desde fuentes oficiales.

    Si no hay resultados responda literalmente: «No se encontró jurisprudencia oficial disponible.»
    """
    res = store.buscar(texto, tipo, limite)
    notas = [] if res else ["No se encontró jurisprudencia oficial disponible."]
    return envelope(
        source="Índice local (cargado por el titular)",
        dataset="indice_local.sqlite",
        url="local",
        results=res,
        notes=notas,
    )


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
def indice_local_estado() -> dict:
    """Cantidad de documentos del índice local por tipo."""
    return store.estadisticas()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--http", action="store_true", help="Sirve por HTTP (conector remoto) en lugar de stdio")
    p.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    a = p.parse_args()
    if a.http:
        mcp.run(transport="http", host=a.host, port=a.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
