"""Índice local SQLite FTS5 para jurisprudencia y normas que el titular cargue desde fuentes oficiales.

Principio: el índice solo contiene lo que el titular ingiere con su URL oficial y fecha de consulta.
La herramienta de búsqueda devuelve esos metadatos junto al texto, de modo que cada resultado es
trazable. No se completan datos faltantes.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import Any

from . import config

CAMPOS = ["tipo", "titulo", "corporacion", "numero", "radicado", "fecha", "ponente", "url_oficial", "fecha_consulta"]


def conectar(path=None) -> sqlite3.Connection:
    con = sqlite3.connect(str(path or config.INDEX_DB))
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS docs(
            id INTEGER PRIMARY KEY,
            tipo TEXT, titulo TEXT, corporacion TEXT, numero TEXT, radicado TEXT,
            fecha TEXT, ponente TEXT, url_oficial TEXT, fecha_consulta TEXT, texto TEXT,
            UNIQUE(url_oficial, titulo)
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
            titulo, corporacion, numero, radicado, ponente, texto,
            content='docs', content_rowid='id', tokenize='unicode61 remove_diacritics 2'
        );
        CREATE TRIGGER IF NOT EXISTS docs_ai AFTER INSERT ON docs BEGIN
            INSERT INTO docs_fts(rowid, titulo, corporacion, numero, radicado, ponente, texto)
            VALUES (new.id, new.titulo, new.corporacion, new.numero, new.radicado, new.ponente, new.texto);
        END;
        """
    )
    return con


def insertar(doc: dict[str, Any], con: sqlite3.Connection | None = None) -> bool:
    """Inserta un documento. Exige url_oficial y fecha_consulta; devuelve False si ya existía."""
    faltan = [k for k in ("titulo", "texto", "url_oficial", "fecha_consulta") if not doc.get(k)]
    if faltan:
        raise ValueError(f"Documento sin campos obligatorios para trazabilidad: {', '.join(faltan)}")
    own = con is None
    con = con or conectar()
    try:
        cols = [*CAMPOS, "texto"]
        cur = con.execute(
            f"INSERT OR IGNORE INTO docs({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            [doc.get(c) for c in cols],
        )
        con.commit()
        return cur.rowcount > 0
    finally:
        if own:
            con.close()


def _fts_query(texto: str) -> str:
    toks = ["".join(ch for ch in t if ch.isalnum()) for t in texto.split()]
    return " ".join(f'"{t}"' for t in toks if t)


def buscar(texto: str, tipo: str = "", limite: int = 10, con: sqlite3.Connection | None = None) -> list[dict]:
    q = _fts_query(texto)
    if not q:
        return []
    own = con is None
    con = con or conectar()
    try:
        sql = (
            "SELECT d.*, snippet(docs_fts, 5, '«', '»', ' … ', 24) AS fragmento "
            "FROM docs_fts JOIN docs d ON d.id = docs_fts.rowid WHERE docs_fts MATCH ?"
        )
        args: list[Any] = [q]
        if tipo:
            sql += " AND d.tipo = ?"
            args.append(tipo)
        sql += " ORDER BY rank LIMIT ?"
        args.append(max(1, min(limite, 50)))
        out = []
        for r in con.execute(sql, args):
            d = {k: r[k] for k in [*CAMPOS, "fragmento"]}
            out.append(d)
        return out
    finally:
        if own:
            con.close()


def estadisticas() -> dict:
    with closing(conectar()) as con:
        n = con.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
        por_tipo = {r[0] or "": r[1] for r in con.execute("SELECT tipo, COUNT(*) FROM docs GROUP BY tipo")}
    return {"documentos": n, "por_tipo": por_tipo}
