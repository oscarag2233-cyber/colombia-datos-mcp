"""Procesos judiciales: Consulta Nacional Unificada de la Rama Judicial.

Endpoint verificado el 2026-10-29 mediante captura en el navegador (consulta por número de
radicación, sin verificación humana en ese momento):

    GET https://consultaprocesos.ramajudicial.gov.co:448/api/v2/Procesos/Consulta/NumeroRadicacion
        ?numero=<23 dígitos>&SoloActivos=<true|false>&pagina=<n>

Es una API interna del portal, no un servicio documentado: puede cambiar sin aviso. La base puede
sobrescribirse con RAMA_API_BASE. Solo se implementa la consulta por radicado (lista de procesos);
el detalle de actuaciones no se ha capturado y no se presume.

No se evade CAPTCHA ni se consultan procesos reservados. Si el portal exige verificación
humana o responde con error, la herramienta devuelve el error sin intentar sortearlo. Cuando un
proceso viene marcado como privado (`esPrivado`), se omiten sus sujetos procesales.
"""

from __future__ import annotations

import re

import httpx

from .. import config
from ..envelope import envelope, error

RADICADO_RE = re.compile(r"^\d{23}$")
PATH = "/Procesos/Consulta/NumeroRadicacion"


def normalizar_respuesta(data: dict) -> dict:
    """Reduce la respuesta del portal a los campos observados y respeta la marca de proceso privado."""
    procesos = []
    for p in data.get("procesos") or []:
        privado = bool(p.get("esPrivado"))
        procesos.append(
            {
                "radicado": p.get("llaveProceso"),
                "id_proceso": p.get("idProceso"),
                "fecha_proceso": p.get("fechaProceso"),
                "fecha_ultima_actuacion": p.get("fechaUltimaActuacion"),
                "despacho": (p.get("despacho") or "").strip(),
                "departamento": p.get("departamento"),
                "sujetos_procesales": None if privado else (p.get("sujetosProcesales") or "").strip(),
                "privado": privado,
            }
        )
    pag = data.get("paginacion") or {}
    return {
        "procesos": procesos,
        "total": pag.get("cantidadRegistros", len(procesos)),
        "pagina": pag.get("pagina"),
        "paginas": pag.get("cantidadPaginas"),
    }


async def consultar_radicado(radicado: str, solo_activos: bool = False, pagina: int = 1) -> dict:
    radicado = re.sub(r"\D", "", radicado)
    if not RADICADO_RE.match(radicado):
        return error("Rama Judicial", "El radicado debe tener 23 dígitos.")
    url = f"{config.RAMA_API_BASE}{PATH}"
    params = {"numero": radicado, "SoloActivos": str(solo_activos).lower(), "pagina": pagina}
    try:
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT, headers={"User-Agent": config.USER_AGENT}) as c:
            r = await c.get(url, params=params)
    except httpx.HTTPError as e:
        return error("Rama Judicial", f"Fallo de red: {type(e).__name__}", hint="El portal puede estar fuera de línea.")
    if r.status_code != 200:
        return error(
            "Rama Judicial",
            f"HTTP {r.status_code}",
            hint="El portal puede exigir verificación humana o haber cambiado la ruta. No se intenta sortear.",
        )
    try:
        data = r.json()
    except ValueError:
        return error("Rama Judicial", "Respuesta no JSON.", hint="Posible verificación humana o cambio del portal.")
    res = normalizar_respuesta(data)
    notas = [
        "API interna del portal verificada el 2026-10-29; puede cambiar sin aviso.",
        "Solo lista procesos por radicado; el detalle de actuaciones no está implementado.",
        "Con SoloActivos=true el portal limita a procesos con actuaciones recientes (30 días); un resultado vacío no prueba que el proceso no exista.",
    ]
    if not res["procesos"]:
        notas.append("Sin resultados para este radicado con los parámetros indicados.")
    return envelope(
        source="Rama Judicial (Consulta Nacional Unificada)",
        dataset="Procesos/Consulta/NumeroRadicacion",
        url=url,
        results=res,
        verified=True,
        notes=notas,
    )


def normalizar_actuaciones(data: dict) -> dict:
    """Reduce la respuesta de Proceso/Actuaciones a los campos observados (verificado el 2026-10-29)."""
    acts = []
    for a in data.get("actuaciones") or []:
        acts.append(
            {
                "consecutivo": a.get("consActuacion"),
                "fecha_actuacion": a.get("fechaActuacion"),
                "actuacion": (a.get("actuacion") or "").strip(),
                "anotacion": (a.get("anotacion") or "").strip() or None,
                "fecha_inicia_termino": a.get("fechaInicial"),
                "fecha_finaliza_termino": a.get("fechaFinal"),
                "fecha_registro": a.get("fechaRegistro"),
                "con_documentos": a.get("conDocumentos"),
            }
        )
    pag = data.get("paginacion") or {}
    return {
        "actuaciones": acts,
        "total": pag.get("cantidadRegistros", len(acts)),
        "pagina": pag.get("pagina"),
        "paginas": pag.get("cantidadPaginas"),
    }


async def consultar_actuaciones(radicado: str, pagina: int = 1) -> dict:
    """Actuaciones de un proceso: primero resuelve el idProceso por radicado y luego pide las actuaciones.

    Endpoint verificado el 2026-10-29: GET /Proceso/Actuaciones/{idProceso}?pagina=n. El portal
    puede tardar en responder; se usa un tiempo de espera ampliado. No se evade ninguna verificación.
    """
    base = await consultar_radicado(radicado, solo_activos=False)
    if "error" in base:
        return base
    procesos = base["results"]["procesos"]
    if not procesos:
        return error("Rama Judicial", "No se encontró el proceso para ese radicado.")
    p = procesos[0]
    if p["privado"]:
        return error("Rama Judicial", "Proceso marcado como privado; no se consultan actuaciones.")
    url = f"{config.RAMA_API_BASE}/Proceso/Actuaciones/{p['id_proceso']}"
    try:
        async with httpx.AsyncClient(timeout=max(config.HTTP_TIMEOUT, 60), headers={"User-Agent": config.USER_AGENT}) as c:
            r = await c.get(url, params={"pagina": pagina})
    except httpx.HTTPError as e:
        return error("Rama Judicial", f"Fallo de red: {type(e).__name__}", hint="El portal puede estar lento o fuera de línea.")
    if r.status_code != 200:
        return error("Rama Judicial", f"HTTP {r.status_code}", hint="No se intenta sortear verificaciones del portal.")
    try:
        res = normalizar_actuaciones(r.json())
    except ValueError:
        return error("Rama Judicial", "Respuesta no JSON.")
    res["radicado"] = p["radicado"]
    res["despacho"] = p["despacho"]
    return envelope(
        source="Rama Judicial (Consulta Nacional Unificada)",
        dataset="Proceso/Actuaciones",
        url=url,
        results=res,
        verified=True,
        notes=[
            "API interna del portal verificada el 2026-10-29; puede cambiar sin aviso.",
            "El portal publica las actuaciones tal como las registra el despacho; no sustituye la consulta del expediente.",
            "No se descargan documentos adjuntos.",
        ],
    )
