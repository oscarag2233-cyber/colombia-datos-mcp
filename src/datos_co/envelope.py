"""Sobre de respuesta común: toda herramienta devuelve fuente, URL, fecha de consulta y notas.

Esto materializa la trazabilidad exigida para trabajo jurídico: cada dato viaja con su origen.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def envelope(
    *,
    source: str,
    dataset: str,
    url: str,
    results: list[dict[str, Any]] | dict[str, Any],
    total: int | None = None,
    as_of: str | None = None,
    verified: bool = True,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "source": source,
        "dataset": dataset,
        "url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": as_of,
        "total": total if total is not None else (len(results) if isinstance(results, list) else None),
        "verified_endpoint": verified,
        "notes": notes or [],
        "results": results,
    }


def error(source: str, message: str, *, hint: str | None = None) -> dict[str, Any]:
    out = {"source": source, "error": message}
    if hint:
        out["hint"] = hint
    return out
