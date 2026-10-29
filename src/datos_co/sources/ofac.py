"""Cribado contra listas OFAC (SDN) usando los archivos públicos del Sanctions List Service.

Formato legado de SDN.CSV (sin encabezado): ent_num, SDN_Name, SDN_Type, Program, Title,
Call_Sign, Vess_type, Tonnage, GRT, Vess_flag, Vess_owner, Remarks.
ALT.CSV: ent_num, alt_num, alt_type, alt_name, alt_remarks.

Un resultado de cribado es un indicio de coincidencia, no una determinación: requiere
validación humana con datos adicionales (fecha de nacimiento, identificación, país).
"""

from __future__ import annotations

import csv
import io
import time
import unicodedata
from pathlib import Path

import httpx
from rapidfuzz import fuzz

from .. import config
from ..envelope import envelope

SDN_COLS = ["ent_num", "name", "type", "program", "title", "call_sign", "vess_type", "tonnage", "grt", "vess_flag", "vess_owner", "remarks"]
ALT_COLS = ["ent_num", "alt_num", "alt_type", "alt_name", "alt_remarks"]


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join("".join(c if c.isalnum() else " " for c in t.lower()).split())


def parse_sdn(csv_text: str) -> list[dict]:
    rows = []
    for rec in csv.reader(io.StringIO(csv_text)):
        if len(rec) < 4 or not rec[0].strip().isdigit():
            continue
        rec = (rec + [""] * len(SDN_COLS))[: len(SDN_COLS)]
        rows.append({k: v.strip() for k, v in zip(SDN_COLS, rec)})
    return rows


def parse_alt(csv_text: str) -> list[dict]:
    rows = []
    for rec in csv.reader(io.StringIO(csv_text)):
        if len(rec) < 4 or not rec[0].strip().isdigit():
            continue
        rec = (rec + [""] * len(ALT_COLS))[: len(ALT_COLS)]
        rows.append({k: v.strip() for k, v in zip(ALT_COLS, rec)})
    return rows


def _cache_path(name: str) -> Path:
    return config.DATA_DIR / f"ofac_{name}.csv"


async def _descargar(url: str, name: str) -> str:
    path = _cache_path(name)
    if path.exists() and (time.time() - path.stat().st_mtime) < config.OFAC_TTL_HORAS * 3600:
        return path.read_text(encoding="utf-8", errors="replace")
    async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT, headers={"User-Agent": config.USER_AGENT}, follow_redirects=True) as c:
        r = await c.get(url)
        r.raise_for_status()
        text = r.text
    path.write_text(text, encoding="utf-8")
    return text


def cribar(nombre: str, sdn: list[dict], alt: list[dict], umbral: int = 85, limite: int = 10) -> list[dict]:
    objetivo = normalizar(nombre)
    if not objetivo:
        return []
    alias_por_ent: dict[str, list[str]] = {}
    for a in alt:
        alias_por_ent.setdefault(a["ent_num"], []).append(a["alt_name"])
    hallazgos = []
    for s in sdn:
        candidatos = [s["name"], *alias_por_ent.get(s["ent_num"], [])]
        mejor, mejor_nombre = 0, ""
        for cand in candidatos:
            score = fuzz.token_sort_ratio(objetivo, normalizar(cand))
            if score > mejor:
                mejor, mejor_nombre = score, cand
        if mejor >= umbral:
            hallazgos.append(
                {
                    "ent_num": s["ent_num"],
                    "score": round(mejor, 1),
                    "nombre_principal": s["name"],
                    "nombre_coincidente": mejor_nombre,
                    "tipo": s["type"],
                    "programas": s["program"],
                    "observaciones": s["remarks"],
                }
            )
    hallazgos.sort(key=lambda h: -h["score"])
    return hallazgos[:limite]


async def screen(nombre: str, umbral: int = 85, limite: int = 10) -> dict:
    sdn = parse_sdn(await _descargar(config.OFAC_SDN_URL, "sdn"))
    try:
        alt = parse_alt(await _descargar(config.OFAC_ALT_URL, "alt"))
        notas = []
    except httpx.HTTPError as e:  # ALT es opcional para no bloquear el cribado
        alt, notas = [], [f"No se pudo descargar ALT.CSV ({e}); se cribó solo contra nombres principales."]
    res = cribar(nombre, sdn, alt, umbral, limite)
    notas.append("Indicio de coincidencia, no determinación. Valide con fecha de nacimiento, identificación y país.")
    p = _cache_path("sdn")
    return envelope(
        source="OFAC Sanctions List Service (SDN)",
        dataset="SDN.CSV + ALT.CSV",
        url=config.OFAC_SDN_URL,
        results=res,
        as_of=time.strftime("%Y-%m-%d", time.gmtime(p.stat().st_mtime)) if p.exists() else None,
        notes=notas,
    )
