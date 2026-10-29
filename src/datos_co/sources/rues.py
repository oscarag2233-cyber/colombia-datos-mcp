"""Empresas: extracto abierto del RUES publicado en datos.gov.co (dataset c82u-588k).

Cubre datos básicos del registro mercantil. NO incluye el certificado de existencia y
representación legal (servicio pagado de las cámaras de comercio) ni, en este dataset, el detalle
de establecimientos (hay un dataset aparte, nb3d-v3n7, no integrado). Un resultado vacío no prueba
que la empresa no exista.

Minimización de datos personales: se seleccionan solo columnas corporativas y el nombre del
representante legal (dato de publicidad registral). No se devuelven números de identificación de
personas naturales ni del representante legal.
"""

from __future__ import annotations

from .. import config, socrata
from ..envelope import envelope, error

SELECT = (
    "matricula,razon_social,sigla,nit,clase_identificacion,numero_identificacion,digito_verificacion,"
    "camara_comercio,organizacion_juridica,tipo_sociedad,categoria_matricula,estado_matricula,"
    "fecha_matricula,fecha_renovacion,ultimo_ano_renovado,fecha_cancelacion,cod_ciiu_act_econ_pri,"
    "representante_legal,fecha_actualizacion"
)


def normalizar_fila(fila: dict) -> dict:
    """Resuelve el NIT y descarta cualquier identificación que no sea NIT.

    Verificado el 2026-10-29: en algunos registros `nit` viene vacío y el NIT está en
    `numero_identificacion` con clase_identificacion = 'NIT'. Si la clase es otra (por ejemplo
    cédula de una persona natural), el número se elimina para no exponer datos personales.
    """
    out = dict(fila)
    clase = (out.get("clase_identificacion") or "").upper()
    numero = out.pop("numero_identificacion", None)
    if not out.get("nit") and clase == "NIT" and numero:
        out["nit"] = numero
    return out


def nit_candidatos(nit: str) -> list[str]:
    """Acepta '900123456-7', '9001234567' o '900123456'. El dataset guarda el NIT sin dígito de verificación."""
    texto = nit.strip()
    if "-" in texto:
        base = "".join(c for c in texto.split("-")[0] if c.isdigit())
        return [base] if base else []
    digitos = "".join(c for c in texto if c.isdigit())
    if not digitos:
        return []
    # Con 10 dígitos es ambiguo (puede incluir el DV): se prueban ambas lecturas.
    return [digitos, digitos[:-1]] if len(digitos) == 10 else [digitos]


async def buscar_empresa(nit: str = "", nombre: str = "", limite: int = 10) -> dict:
    ds = config.DATASETS["rues_abierto"]
    if not ds:
        return error("RUES abierto", "Dataset no configurado (DS_RUES_ABIERTO).")
    if not nit and not nombre:
        return error("RUES abierto", "Indique un NIT o un nombre.")
    clauses = []
    if nit:
        cands = nit_candidatos(nit)
        if not cands:
            return error("RUES abierto", "NIT inválido.")
        lista = ", ".join(socrata.sql_quote(c) for c in cands)
        clauses.append(
            f"({config.RUES_COL_NIT} in ({lista}) OR "
            f"(clase_identificacion = 'NIT' AND numero_identificacion in ({lista})))"
        )
    if nombre:
        clauses.append(f"upper({config.RUES_COL_NOMBRE}) like {socrata.sql_quote('%' + nombre.upper() + '%')}")
    rows = await socrata.query(ds, where=socrata.build_where(clauses), select=SELECT, limit=limite)
    return envelope(
        source="RUES abierto (datos.gov.co, serviciorues)",
        dataset=ds,
        url=socrata.resource_url(ds),
        results=[normalizar_fila(r) for r in rows],
        notes=[
            "Extracto de datos básicos; no sustituye el certificado de existencia y representación legal.",
            "Columnas verificadas el 2026-10-29; consulta por nombre y NIT probada en vivo.",
            "No se devuelven números de identificación de personas naturales ni del representante legal.",
        ],
    )
