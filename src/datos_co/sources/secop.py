"""Contratación pública (SECOP II) vía datos.gov.co.

Verificado el 2026-10-29 contra los metadatos vivos (api/views/<id>.json):
  * jbjy-vk9h «SECOP II - Contratos Electrónicos»: existen nombre_entidad, nit_entidad (NUMÉRICO),
    departamento, fecha_de_firma, documento_proveedor, proveedor_adjudicado, valor_del_contrato.
  * p6dx-8zbt «SECOP II - Procesos de Contratación»: nit_entidad es TEXTO.
Las consultas SoQL (filtros) aún no se ejecutaron en vivo desde este entorno.
Los nombres se centralizan en COLS; `secop_describir_dataset` permite revalidarlos.
"""

from __future__ import annotations

from .. import config, socrata
from ..envelope import envelope

COLS = {
    "nit_entidad": "nit_entidad",
    "entidad": "nombre_entidad",
    "proveedor_doc": "documento_proveedor",
    "proveedor": "proveedor_adjudicado",
    "departamento": "departamento",
    "fecha_firma": "fecha_de_firma",
    "valor": "valor_del_contrato",
}

NOTA_VALIDACION = (
    "Columnas verificadas contra el esquema vivo el 2026-10-29; los filtros no se probaron en vivo. "
    "Si una consulta falla, ejecute secop_describir_dataset y ajuste COLS en sources/secop.py."
)


def _clean_doc(value: str) -> str:
    return "".join(ch for ch in value if ch.isalnum())


async def buscar_contratos(
    texto: str = "",
    documento_proveedor: str = "",
    nit_entidad: str = "",
    departamento: str = "",
    desde: str = "",
    hasta: str = "",
    limite: int = 20,
    pagina: int = 1,
) -> dict:
    ds = config.DATASETS["secop2_contratos"]
    clauses: list[str] = []
    if documento_proveedor:
        clauses.append(f"{COLS['proveedor_doc']} = {socrata.sql_quote(_clean_doc(documento_proveedor))}")
    if nit_entidad:
        nit = "".join(ch for ch in nit_entidad if ch.isdigit())
        if nit:  # en este dataset nit_entidad es numérico (verificado 2026-10-29)
            clauses.append(f"{COLS['nit_entidad']} = {int(nit)}")
    if departamento:
        clauses.append(f"upper({COLS['departamento']}) = {socrata.sql_quote(departamento.upper())}")
    if desde:
        clauses.append(f"{COLS['fecha_firma']} >= {socrata.sql_quote(desde + 'T00:00:00')}")
    if hasta:
        clauses.append(f"{COLS['fecha_firma']} <= {socrata.sql_quote(hasta + 'T23:59:59')}")
    rows = await socrata.query(
        ds,
        where=socrata.build_where(clauses),
        q=texto or None,
        order=f"{COLS['fecha_firma']} DESC",
        limit=limite,
        offset=(max(pagina, 1) - 1) * limite,
    )
    return envelope(
        source="SECOP II (datos.gov.co)",
        dataset=ds,
        url=socrata.resource_url(ds),
        results=rows,
        verified=False,
        notes=[NOTA_VALIDACION],
    )


async def buscar_procesos(texto: str = "", nit_entidad: str = "", limite: int = 20, pagina: int = 1) -> dict:
    ds = config.DATASETS["secop2_procesos"]
    clauses = []
    if nit_entidad:
        clauses.append(f"nit_entidad = {socrata.sql_quote(_clean_doc(nit_entidad))}")
    rows = await socrata.query(
        ds,
        where=socrata.build_where(clauses),
        q=texto or None,
        limit=limite,
        offset=(max(pagina, 1) - 1) * limite,
    )
    return envelope(
        source="SECOP II procesos (datos.gov.co)",
        dataset=ds,
        url=socrata.resource_url(ds),
        results=rows,
        verified=False,
        notes=[NOTA_VALIDACION],
    )


async def describir(dataset_key: str = "secop2_contratos") -> dict:
    ds = config.DATASETS.get(dataset_key) or dataset_key
    meta = await socrata.describe(ds)
    return envelope(
        source="datos.gov.co (metadatos)", dataset=ds, url=meta["url"], results=meta, as_of=str(meta.get("rowsUpdatedAt"))
    )
