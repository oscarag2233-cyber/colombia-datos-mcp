"""Pruebas de las 9 herramientas MCP, invocadas por su nombre a través del cliente en memoria.

Ninguna prueba sale a la red: toda petición de httpx se atiende con httpx.MockTransport y cualquier
URL no prevista hace fallar la prueba. El índice local y la caché de OFAC se redirigen a tmp_path.
"""

from __future__ import annotations

import httpx
import pytest
from fastmcp import Client

from datos_co import config, store
from datos_co.server import mcp

EXTERNAS = {
    "secop_buscar_contratos",
    "secop_buscar_procesos",
    "secop_describir_dataset",
    "sanciones_ofac_cribar",
    "empresas_buscar",
    "procesos_consultar_radicado",
    "procesos_actuaciones",
}
LOCALES = {"jurisprudencia_buscar_local", "indice_local_estado"}
_ASYNC_CLIENT_REAL = httpx.AsyncClient
PISTAS = ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint")

RADICADO = "66001310300320250039900"
SDN = (
    '36,"AEROCARIBBEAN AIRLINES","-0- ","CUBA",-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,"Linked To: X."\n'
    '1001,"PEREZ GOMEZ, Juan Carlos","individual","SDNTK",-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,"DOB 01 Jan 1970"\n'
)
ALT = '1001,5,"aka","JUAN CARLOS PEREZ",-0- \n'


@pytest.fixture(autouse=True)
def datos_aislados(tmp_path, monkeypatch):
    """Redirige la caché de OFAC y el índice local a un directorio temporal."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "INDEX_DB", tmp_path / "indice_local.sqlite")
    return tmp_path


@pytest.fixture(autouse=True)
def sin_red(monkeypatch):
    """Por defecto, cualquier petición HTTP hace fallar la prueba."""

    def rechazar(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Petición de red no simulada: {request.url}")

    _instalar(monkeypatch, rechazar)


def _instalar(monkeypatch, handler):
    def fabrica(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return _ASYNC_CLIENT_REAL(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", fabrica)


@pytest.fixture
def red_simulada(monkeypatch):
    """Instala un manejador que responde las peticiones y registra las recibidas."""

    def instalar(handler):
        recibidas: list[httpx.Request] = []

        def registrar(request: httpx.Request) -> httpx.Response:
            recibidas.append(request)
            return handler(request)

        _instalar(monkeypatch, registrar)
        return recibidas

    return instalar


async def llamar(nombre: str, argumentos: dict | None = None) -> dict:
    async with Client(mcp) as cliente:
        resultado = await cliente.call_tool(nombre, argumentos or {})
    return resultado.structured_content


# ---------------------------------------------------------------- anotaciones


async def test_las_9_herramientas_declaran_las_cuatro_pistas_como_booleanos():
    async with Client(mcp) as cliente:
        herramientas = {h.name: h for h in await cliente.list_tools()}
    assert set(herramientas) == EXTERNAS | LOCALES
    for nombre, h in herramientas.items():
        assert h.annotations is not None, nombre
        # Se leen con el nombre del protocolo (camelCase), tal como las recibe el cliente MCP.
        pistas = h.annotations.model_dump(by_alias=True)
        for pista in PISTAS:
            assert isinstance(pistas.get(pista), bool), f"{nombre}.{pista} = {pistas.get(pista)!r}"
        assert pistas["readOnlyHint"] is True, nombre
        assert pistas["destructiveHint"] is False, nombre
        assert pistas["idempotentHint"] is True, nombre
        assert pistas["openWorldHint"] is (nombre in EXTERNAS), nombre


# ---------------------------------------------------------------------- SECOP


async def test_secop_buscar_contratos(red_simulada):
    fila = {"nombre_entidad": "MUNICIPIO X", "valor_del_contrato": "1000"}
    recibidas = red_simulada(lambda req: httpx.Response(200, json=[fila]))
    r = await llamar(
        "secop_buscar_contratos",
        {"texto": "vigilancia", "nit_entidad": "891.480.030-2", "departamento": "Risaralda", "desde": "2026-01-01", "pagina": 2, "limite": 5},
    )
    assert r["results"] == [fila] and r["total"] == 1
    assert r["verified_endpoint"] is False and r["dataset"] == "jbjy-vk9h"
    (req,) = recibidas
    assert req.method == "GET" and req.url.host == "www.datos.gov.co"
    assert req.url.path == "/resource/jbjy-vk9h.json"
    p = req.url.params
    assert p["$q"] == "vigilancia" and p["$limit"] == "5" and p["$offset"] == "5"
    assert "nit_entidad = 8914800302" in p["$where"]
    assert "upper(departamento) = 'RISARALDA'" in p["$where"]
    assert "fecha_de_firma >= '2026-01-01T00:00:00'" in p["$where"]


async def test_secop_buscar_contratos_devuelve_error_si_falla_la_fuente(red_simulada):
    red_simulada(lambda req: httpx.Response(400, json={"message": "columna inexistente"}))
    r = await llamar("secop_buscar_contratos", {"texto": "x"})
    assert r["source"] == "SECOP II" and "error" in r and "secop_describir_dataset" in r["hint"]


async def test_secop_buscar_procesos(red_simulada):
    fila = {"entidad": "GOBERNACIÓN Y", "nit_entidad": "800100200"}
    recibidas = red_simulada(lambda req: httpx.Response(200, json=[fila]))
    r = await llamar("secop_buscar_procesos", {"texto": "licitación", "nit_entidad": "800.100.200"})
    assert r["results"] == [fila] and r["dataset"] == "p6dx-8zbt"
    (req,) = recibidas
    assert req.url.path == "/resource/p6dx-8zbt.json"
    assert req.url.params["$where"] == "nit_entidad = '800100200'"  # en este dataset el NIT es texto


async def test_secop_describir_dataset(red_simulada):
    meta = {
        "name": "SECOP II - Contratos Electrónicos",
        "attribution": "ANCP-CCE",
        "rowsUpdatedAt": 1761696000,
        "columns": [{"fieldName": "nit_entidad", "name": "Nit Entidad", "dataTypeName": "number"}],
    }
    recibidas = red_simulada(lambda req: httpx.Response(200, json=meta))
    r = await llamar("secop_describir_dataset", {"dataset": "secop2_contratos"})
    assert recibidas[0].url.path == "/api/views/jbjy-vk9h.json"
    assert r["results"]["columns"] == [{"field": "nit_entidad", "label": "Nit Entidad", "type": "number"}]
    assert r["as_of"] == "1761696000"


# ----------------------------------------------------------------------- OFAC


def _ofac(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("SDN.CSV"):
        return httpx.Response(200, text=SDN)
    if request.url.path.endswith("ALT.CSV"):
        return httpx.Response(200, text=ALT)
    return httpx.Response(404)


async def test_sanciones_ofac_cribar(red_simulada):
    recibidas = red_simulada(_ofac)
    r = await llamar("sanciones_ofac_cribar", {"nombre": "Juan Carlos Pérez"})
    assert r["results"][0]["ent_num"] == "1001"
    assert r["results"][0]["nombre_coincidente"] == "JUAN CARLOS PEREZ"
    assert any("Indicio de coincidencia" in n for n in r["notes"])
    assert len(recibidas) == 2  # SDN.CSV y ALT.CSV


async def test_sanciones_ofac_cribar_es_idempotente_y_usa_la_cache(red_simulada, datos_aislados):
    recibidas = red_simulada(_ofac)
    primera = await llamar("sanciones_ofac_cribar", {"nombre": "Juan Carlos Pérez"})
    segunda = await llamar("sanciones_ofac_cribar", {"nombre": "Juan Carlos Pérez"})
    assert primera["results"] == segunda["results"]
    assert len(recibidas) == 2  # la segunda llamada se sirve de la caché local, sin nuevas peticiones
    assert sorted(p.name for p in datos_aislados.glob("ofac_*.csv")) == ["ofac_alt.csv", "ofac_sdn.csv"]


async def test_sanciones_ofac_cribar_sin_coincidencias(red_simulada):
    red_simulada(_ofac)
    r = await llamar("sanciones_ofac_cribar", {"nombre": "Empresa Inexistente SAS"})
    assert r["results"] == [] and r["total"] == 0


# ----------------------------------------------------------------------- RUES


async def test_empresas_buscar(red_simulada):
    filas = [
        {"razon_social": "EMPRESA X SAS", "nit": "", "clase_identificacion": "NIT", "numero_identificacion": "900123456"},
        {"razon_social": "PERSONA NATURAL", "clase_identificacion": "CEDULA DE CIUDADANIA", "numero_identificacion": "123"},
    ]
    recibidas = red_simulada(lambda req: httpx.Response(200, json=filas))
    r = await llamar("empresas_buscar", {"nit": "900.123.456-7"})
    assert r["results"][0]["nit"] == "900123456"
    assert all("numero_identificacion" not in fila for fila in r["results"])  # minimización de datos personales
    (req,) = recibidas
    assert req.url.path == "/resource/c82u-588k.json"
    assert "'900123456'" in req.url.params["$where"]


async def test_empresas_buscar_exige_nit_o_nombre():
    r = await llamar("empresas_buscar", {})  # sin red: la validación ocurre antes de consultar
    assert r == {"source": "RUES abierto", "error": "Indique un NIT o un nombre."}


# -------------------------------------------------------------- Rama Judicial

PROCESO = {
    "idProceso": 777,
    "llaveProceso": RADICADO,
    "fechaProceso": "2025-12-12T00:00:00",
    "fechaUltimaActuacion": "2026-07-30T00:00:00",
    "despacho": "JUZGADO 003 CIVIL DEL CIRCUITO ",
    "departamento": "RISARALDA",
    "sujetosProcesales": "Demandante: A | Demandado: B ",
    "esPrivado": False,
}
PAGINACION = {"cantidadRegistros": 1, "pagina": 1, "cantidadPaginas": 1}


def _rama(proceso: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/Procesos/Consulta/NumeroRadicacion"):
            return httpx.Response(200, json={"procesos": [proceso], "paginacion": PAGINACION})
        if request.url.path.endswith(f"/Proceso/Actuaciones/{proceso['idProceso']}"):
            actuaciones = [
                {"consActuacion": 2, "fechaActuacion": "2026-01-01T00:00:00", "actuacion": "Auto admite ", "anotacion": "Texto ", "conDocumentos": False},
                {"consActuacion": 1, "fechaActuacion": "2025-12-12T00:00:00", "actuacion": "Reparto", "anotacion": None, "conDocumentos": False},
            ]
            return httpx.Response(200, json={"actuaciones": actuaciones, "paginacion": {**PAGINACION, "cantidadRegistros": 2}})
        return httpx.Response(404)

    return handler


async def test_procesos_consultar_radicado(red_simulada):
    recibidas = red_simulada(_rama(PROCESO))
    r = await llamar("procesos_consultar_radicado", {"radicado": RADICADO, "solo_activos": True})
    proceso = r["results"]["procesos"][0]
    assert proceso["radicado"] == RADICADO and proceso["despacho"] == "JUZGADO 003 CIVIL DEL CIRCUITO"
    assert proceso["sujetos_procesales"] == "Demandante: A | Demandado: B"
    (req,) = recibidas
    assert req.method == "GET" and req.url.host == "consultaprocesos.ramajudicial.gov.co"
    assert req.url.params["numero"] == RADICADO and req.url.params["SoloActivos"] == "true"


async def test_procesos_consultar_radicado_rechaza_radicado_invalido():
    r = await llamar("procesos_consultar_radicado", {"radicado": "12345"})  # sin red
    assert r["error"] == "El radicado debe tener 23 dígitos."


async def test_procesos_consultar_radicado_no_sortea_verificacion_humana(red_simulada):
    red_simulada(lambda req: httpx.Response(403, text="captcha"))
    r = await llamar("procesos_consultar_radicado", {"radicado": RADICADO})
    assert r["error"] == "HTTP 403" and "No se intenta sortear" in r["hint"]


async def test_procesos_actuaciones(red_simulada):
    recibidas = red_simulada(_rama(PROCESO))
    r = await llamar("procesos_actuaciones", {"radicado": RADICADO})
    res = r["results"]
    assert res["radicado"] == RADICADO and res["total"] == 2
    assert [a["actuacion"] for a in res["actuaciones"]] == ["Auto admite", "Reparto"]
    assert res["actuaciones"][1]["anotacion"] is None
    assert [req.url.path.rsplit("/", 1)[-1] for req in recibidas] == ["NumeroRadicacion", "777"]


async def test_procesos_actuaciones_omite_proceso_privado(red_simulada):
    recibidas = red_simulada(_rama({**PROCESO, "esPrivado": True}))
    r = await llamar("procesos_actuaciones", {"radicado": RADICADO})
    assert r["error"] == "Proceso marcado como privado; no se consultan actuaciones."
    assert len(recibidas) == 1  # no se llega a pedir las actuaciones


# --------------------------------------------------------------- índice local


def _cargar_documento():
    assert store.insertar(
        {
            "tipo": "sentencia",
            "titulo": "Ejemplo de prueba",
            "texto": "La responsabilidad médica exige acreditar el nexo causal.",
            "url_oficial": "https://example.org/oficial",
            "fecha_consulta": "2026-10-29",
        }
    )


async def test_jurisprudencia_buscar_local():
    _cargar_documento()
    r = await llamar("jurisprudencia_buscar_local", {"texto": "nexo causal"})  # sin red
    assert r["total"] == 1 and r["notes"] == [] and r["url"] == "local"
    assert r["results"][0]["url_oficial"] == "https://example.org/oficial"
    assert r["results"][0]["fecha_consulta"] == "2026-10-29"


async def test_jurisprudencia_buscar_local_sin_resultados():
    r = await llamar("jurisprudencia_buscar_local", {"texto": "inexistente"})
    assert r["results"] == []
    assert r["notes"] == ["No se encontró jurisprudencia oficial disponible."]


async def test_indice_local_estado():
    assert await llamar("indice_local_estado") == {"documentos": 0, "por_tipo": {}}  # sin red
    _cargar_documento()
    assert await llamar("indice_local_estado") == {"documentos": 1, "por_tipo": {"sentencia": 1}}
