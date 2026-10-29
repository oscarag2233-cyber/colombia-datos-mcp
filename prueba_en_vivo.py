"""Prueba en vivo de colombia-datos-mcp contra datos.gov.co y OFAC.

Uso (con el entorno virtual activado y dentro de la carpeta del proyecto):
    python prueba_en_vivo.py
"""

import asyncio
import json
import os

from datos_co.sources import ofac, rama_judicial, rues, secop


async def paso(nombre, coro, resumen):
    print(f"\n=== {nombre} ===")
    try:
        r = await coro
        if "error" in r:
            print("ERROR:", r["error"], r.get("hint", ""))
            return
        print(resumen(r))
    except Exception as e:  # noqa: BLE001
        print("FALLO:", type(e).__name__, str(e)[:300])


# Radicado público de 23 dígitos para la prueba de Rama Judicial. Defínalo en su entorno:
#   export RADICADO_PRUEBA=<23 dígitos>
RADICADO = os.getenv("RADICADO_PRUEBA", "").strip()


async def main():
    await paso(
        "SECOP II: contratos por texto",
        secop.buscar_contratos(texto="consultoria", limite=2),
        lambda r: f"{len(r['results'])} contratos. Campos: {sorted(r['results'][0])[:8] if r['results'] else 'sin resultados'}",
    )
    await paso(
        "SECOP II: contratos por fechas",
        secop.buscar_contratos(desde="2025-01-01", hasta="2025-01-31", limite=2),
        lambda r: f"{len(r['results'])} contratos en enero de 2025",
    )
    await paso(
        "SECOP II: procesos",
        secop.buscar_procesos(texto="software", limite=2),
        lambda r: f"{len(r['results'])} procesos",
    )
    await paso(
        "RUES abierto: por nombre",
        rues.buscar_empresa(nombre="ECOPETROL", limite=3),
        lambda r: "; ".join(f"{x.get('razon_social')} (NIT {x.get('nit')}, {x.get('estado_matricula')})" for x in r["results"])
        or "sin resultados",
    )
    await paso(
        "RUES abierto: por NIT",
        rues.buscar_empresa(nit="899999068", limite=3),
        lambda r: "; ".join(str(x.get("razon_social")) for x in r["results"]) or "sin resultados",
    )
    if RADICADO:
        await paso(
            "Rama Judicial: radicado",
            rama_judicial.consultar_radicado(RADICADO),
            lambda r: "; ".join(
                f"{x['radicado']} | {x['despacho']} | ultima actuacion {x['fecha_ultima_actuacion']}"
                for x in r["results"]["procesos"]
            )
            or "sin resultados",
        )
        await paso(
            "Rama Judicial: actuaciones",
            rama_judicial.consultar_actuaciones(RADICADO),
            lambda r: (
                f"{r['results']['total']} actuaciones; ultima: "
                f"{r['results']['actuaciones'][0]['fecha_actuacion']} {r['results']['actuaciones'][0]['actuacion']}"
            )
            if r["results"]["actuaciones"]
            else "sin actuaciones",
        )
    else:
        print("\n(Rama Judicial omitida: defina RADICADO_PRUEBA con un radicado público de 23 dígitos.)")
    await paso(
        "OFAC: cribado (descarga archivos, puede tardar)",
        ofac.screen("Aerocaribbean Airlines", umbral=85, limite=3),
        lambda r: json.dumps(r["results"][:2], ensure_ascii=False)[:400] or "sin coincidencias",
    )
    print("\nListo. Copie y envíe el resultado completo si algo falló.")


asyncio.run(main())
