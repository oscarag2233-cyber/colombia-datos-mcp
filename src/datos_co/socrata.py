"""Cliente mínimo para la API SODA (Socrata) de datos.gov.co."""

from __future__ import annotations

from typing import Any

import httpx

from . import config


def sql_quote(value: str) -> str:
    """Escapa comillas simples para SoQL."""
    return "'" + value.replace("'", "''") + "'"


def build_where(clauses: list[str]) -> str | None:
    clauses = [c for c in clauses if c]
    return " AND ".join(clauses) if clauses else None


def headers() -> dict[str, str]:
    h = {"User-Agent": config.USER_AGENT, "Accept": "application/json"}
    if config.SOCRATA_APP_TOKEN:
        h["X-App-Token"] = config.SOCRATA_APP_TOKEN
    return h


def resource_url(dataset_id: str) -> str:
    return f"https://{config.SOCRATA_DOMAIN}/resource/{dataset_id}.json"


async def query(
    dataset_id: str,
    *,
    where: str | None = None,
    q: str | None = None,
    select: str | None = None,
    order: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"$limit": max(1, min(limit, 100)), "$offset": max(0, offset)}
    if where:
        params["$where"] = where
    if q:
        params["$q"] = q
    if select:
        params["$select"] = select
    if order:
        params["$order"] = order
    async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT, headers=headers()) as client:
        r = await client.get(resource_url(dataset_id), params=params)
        r.raise_for_status()
        return r.json()


async def describe(dataset_id: str) -> dict[str, Any]:
    """Metadatos y columnas reales del dataset (sirve para validar nombres de campo)."""
    url = f"https://{config.SOCRATA_DOMAIN}/api/views/{dataset_id}.json"
    async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT, headers=headers()) as client:
        r = await client.get(url)
        r.raise_for_status()
        meta = r.json()
    return {
        "name": meta.get("name"),
        "attribution": meta.get("attribution"),
        "rowsUpdatedAt": meta.get("rowsUpdatedAt"),
        "columns": [
            {"field": c.get("fieldName"), "label": c.get("name"), "type": c.get("dataTypeName")}
            for c in meta.get("columns", [])
        ],
        "url": url,
    }
