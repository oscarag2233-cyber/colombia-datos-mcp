"""Configuración por variables de entorno. Nada sensible va en el repositorio."""

from __future__ import annotations

import os
from pathlib import Path

DATA_DIR = Path(os.getenv("DATOS_CO_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

SOCRATA_DOMAIN = os.getenv("SOCRATA_DOMAIN", "www.datos.gov.co")
SOCRATA_APP_TOKEN = os.getenv("SOCRATA_APP_TOKEN", "")  # opcional, sube el límite de peticiones

HTTP_TIMEOUT = float(os.getenv("DATOS_CO_HTTP_TIMEOUT", "30"))
USER_AGENT = os.getenv("DATOS_CO_USER_AGENT", "colombia-datos-mcp/0.1 (legal research; owner contact)")

# Identificadores de datasets de datos.gov.co. Los de SECOP provienen de documentación
# de terceros y deben confirmarse con la herramienta `secop_describir_dataset`.
DATASETS = {
    "secop2_contratos": os.getenv("DS_SECOP2_CONTRATOS", "jbjy-vk9h"),
    "secop2_procesos": os.getenv("DS_SECOP2_PROCESOS", "p6dx-8zbt"),
    # «Personas Naturales, Personas Jurídicas y Entidades Sin Animo de Lucro» (RUES), publicado en
    # datos.gov.co por «serviciorues». ID y columnas verificados el 2026-10-29 contra api/views.
    "rues_abierto": os.getenv("DS_RUES_ABIERTO", "c82u-588k"),
}

# Columnas de RUES abierto (verificadas: ambas son texto; el NIT no incluye dígito de verificación).
RUES_COL_NIT = os.getenv("RUES_COL_NIT", "nit")
RUES_COL_NOMBRE = os.getenv("RUES_COL_NOMBRE", "razon_social")

# OFAC: archivos públicos del Sanctions List Service (sin autenticación).
OFAC_SDN_URL = os.getenv(
    "OFAC_SDN_URL", "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV"
)
OFAC_ALT_URL = os.getenv(
    "OFAC_ALT_URL", "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/ALT.CSV"
)
OFAC_TTL_HORAS = int(os.getenv("OFAC_TTL_HORAS", "24"))

# Rama Judicial: la URL base de la API interna se captura con DevTools (XHR) y se define aquí.
RAMA_API_BASE = os.getenv("RAMA_API_BASE", "https://consultaprocesos.ramajudicial.gov.co:448/api/v2").rstrip("/")

INDEX_DB = Path(os.getenv("DATOS_CO_INDEX_DB", DATA_DIR / "indice_local.sqlite"))
