"""Carga de documentos al índice local.

Uso:
    colombia-datos-ingest ruta/a/carpeta_o_archivo.jsonl

Formatos admitidos:
  * .jsonl, un objeto por línea con las claves de store.CAMPOS más `texto`.
  * .md / .txt con encabezado `clave: valor` (una por línea) y una línea en blanco antes del texto.

Obligatorios: titulo, texto, url_oficial, fecha_consulta. Sin ellos el documento se rechaza,
porque un dato sin fuente oficial y fecha de consulta no es utilizable en trabajo jurídico.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from . import store


def _leer_texto(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    cabecera, _, cuerpo = raw.partition("\n\n")
    doc: dict = {}
    for linea in cabecera.splitlines():
        if ":" in linea:
            k, v = linea.split(":", 1)
            doc[k.strip().lower()] = v.strip()
    doc["texto"] = cuerpo.strip()
    doc.setdefault("titulo", path.stem)
    return doc


def _documentos(ruta: Path):
    archivos = [ruta] if ruta.is_file() else sorted(p for p in ruta.rglob("*") if p.suffix in {".jsonl", ".md", ".txt"})
    for a in archivos:
        if a.suffix == ".jsonl":
            for n, linea in enumerate(a.read_text(encoding="utf-8").splitlines(), 1):
                if linea.strip():
                    yield f"{a.name}:{n}", json.loads(linea)
        else:
            yield a.name, _leer_texto(a)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    ok = dup = bad = 0
    con = store.conectar()
    for origen, doc in _documentos(Path(argv[0])):
        try:
            if store.insertar(doc, con):
                ok += 1
            else:
                dup += 1
        except ValueError as e:
            bad += 1
            print(f"RECHAZADO {origen}: {e}")
    con.close()
    print(f"Insertados: {ok} | duplicados: {dup} | rechazados: {bad}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
