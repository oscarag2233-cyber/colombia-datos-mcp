import pytest

from datos_co import socrata, store
from datos_co.sources import ofac

SDN = (
    '36,"AEROCARIBBEAN AIRLINES","-0- ","CUBA",-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,"Linked To: X."\n'
    '1001,"PEREZ GOMEZ, Juan Carlos","individual","SDNTK",-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,"DOB 01 Jan 1970"\n'
)
ALT = '1001,5,"aka","JUAN CARLOS PEREZ",-0- \n'


def test_normalizar_quita_tildes_y_signos():
    assert ofac.normalizar("Pérez-Gómez, JOSÉ") == "perez gomez jose"


def test_parse_sdn_y_alt():
    assert [r["ent_num"] for r in ofac.parse_sdn(SDN)] == ["36", "1001"]
    assert ofac.parse_alt(ALT)[0]["alt_name"] == "JUAN CARLOS PEREZ"


def test_cribar_coincide_por_alias_y_orden():
    sdn, alt = ofac.parse_sdn(SDN), ofac.parse_alt(ALT)
    res = ofac.cribar("Juan Carlos Pérez", sdn, alt, umbral=85)
    assert res and res[0]["ent_num"] == "1001"
    assert ofac.cribar("Empresa Inexistente SAS", sdn, alt, umbral=85) == []


def test_soql_escapa_comillas():
    assert socrata.sql_quote("O'Brien") == "'O''Brien'"
    assert socrata.build_where(["a = 1", "", "b = 2"]) == "a = 1 AND b = 2"


def test_indice_exige_trazabilidad(tmp_path):
    con = store.conectar(tmp_path / "t.sqlite")
    with pytest.raises(ValueError):
        store.insertar({"titulo": "T-1", "texto": "algo"}, con)
    ok = store.insertar(
        {
            "tipo": "sentencia",
            "titulo": "Ejemplo",
            "texto": "La responsabilidad médica exige acreditar el nexo causal.",
            "url_oficial": "https://example.org/oficial",
            "fecha_consulta": "2026-10-29",
        },
        con,
    )
    assert ok
    assert not store.insertar(
        {"titulo": "Ejemplo", "texto": "x", "url_oficial": "https://example.org/oficial", "fecha_consulta": "2026-10-29"}, con
    )
    hits = store.buscar("nexo causal", con=con)
    assert hits and hits[0]["url_oficial"] == "https://example.org/oficial"
    assert store.buscar("inexistente", con=con) == []


def test_nit_candidatos():
    from datos_co.sources import rues

    assert rues.nit_candidatos("900.123.456-7") == ["900123456"]
    assert rues.nit_candidatos("9001234567") == ["9001234567", "900123456"]
    assert rues.nit_candidatos("900123456") == ["900123456"]
    assert rues.nit_candidatos("abc") == []


def test_normalizar_fila_nit_y_privacidad():
    from datos_co.sources import rues

    # NIT vacío, pero el número está en numero_identificacion con clase NIT: se resuelve.
    f = rues.normalizar_fila({"razon_social": "X", "clase_identificacion": "NIT", "numero_identificacion": "800051785"})
    assert f["nit"] == "800051785" and "numero_identificacion" not in f
    # Persona natural (cédula): el número se descarta y no se confunde con NIT.
    p = rues.normalizar_fila({"razon_social": "Y", "clase_identificacion": "CEDULA DE CIUDADANIA", "numero_identificacion": "123"})
    assert "nit" not in p and "numero_identificacion" not in p
    # Si ya hay nit, se conserva.
    assert rues.normalizar_fila({"nit": "1", "clase_identificacion": "NIT", "numero_identificacion": "2"})["nit"] == "1"


def test_rama_normalizar_respuesta_y_privados():
    from datos_co.sources import rama_judicial as rj

    data = {
        "procesos": [
            {"idProceso": 1, "llaveProceso": "00000000000000000000000", "fechaProceso": "2025-12-12T00:00:00",
             "fechaUltimaActuacion": "2026-07-30T00:00:00", "despacho": "JUZGADO X ", "departamento": "RISARALDA",
             "sujetosProcesales": "Demandante: A | Demandado: B ", "esPrivado": False},
            {"idProceso": 2, "llaveProceso": "66001310300320250039901", "despacho": "Y", "sujetosProcesales": "Reservado", "esPrivado": True},
        ],
        "paginacion": {"cantidadRegistros": 2, "pagina": 1, "cantidadPaginas": 1},
    }
    r = rj.normalizar_respuesta(data)
    assert r["total"] == 2 and r["procesos"][0]["despacho"] == "JUZGADO X"
    assert r["procesos"][0]["sujetos_procesales"] == "Demandante: A | Demandado: B"
    assert r["procesos"][1]["privado"] is True and r["procesos"][1]["sujetos_procesales"] is None


def test_rama_normalizar_actuaciones():
    from datos_co.sources import rama_judicial as rj

    data = {
        "actuaciones": [
            {"consActuacion": 2, "fechaActuacion": "2026-01-01T00:00:00", "actuacion": "Auto X ", "anotacion": "Texto ",
             "fechaInicial": None, "fechaFinal": None, "fechaRegistro": "2026-01-01T00:00:00", "conDocumentos": False},
            {"consActuacion": 1, "fechaActuacion": "2025-12-01T00:00:00", "actuacion": "Reparto", "anotacion": None,
             "fechaRegistro": "2025-12-01T00:00:00", "conDocumentos": False},
        ],
        "paginacion": {"cantidadRegistros": 2, "pagina": 1, "cantidadPaginas": 1},
    }
    r = rj.normalizar_actuaciones(data)
    assert r["total"] == 2 and r["actuaciones"][0]["actuacion"] == "Auto X"
    assert r["actuaciones"][1]["anotacion"] is None
