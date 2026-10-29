# colombia-datos-mcp

Servidor MCP propio con datos públicos de Colombia (contratación, sanciones, empresas, procesos judiciales, jurisprudencia y normas), pensado para usarse desde Claude y ChatGPT sin intermediarios de pago. Cada respuesta incluye fuente, URL, fecha de consulta y una marca de si el endpoint está verificado.

Borrador técnico sujeto a revisión del abogado responsable. Arquitectura y alcance: [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

## Herramientas

| Herramienta | Fuente | Estado |
|---|---|---|
| `secop_buscar_contratos` | SECOP II, datos.gov.co | Columnas verificadas; filtros por probar en vivo |
| `secop_buscar_procesos` | SECOP II, datos.gov.co | Ídem |
| `secop_describir_dataset` | Metadatos de datos.gov.co | Para validar columnas |
| `sanciones_ofac_cribar` | OFAC (SDN y alias) | Probado con datos sintéticos |
| `empresas_buscar` | Extracto abierto RUES (`c82u-588k`) | Columnas verificadas; consulta por probar en vivo |
| `procesos_consultar_radicado` | Rama Judicial | Listo (endpoint verificado el 2026-10-29) |
| `procesos_actuaciones` | Rama Judicial | Listo (endpoint verificado el 2026-10-29) |
| `jurisprudencia_buscar_local` | Índice local SQLite | Requiere ingesta propia |

Todas son de solo lectura.

## Instalación

```bash
git clone https://github.com/oscarag2233-cyber/colombia-datos-mcp.git && cd colombia-datos-mcp
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env     # complete lo que aplique
pytest
```

## Uso con asistentes de IA

Cada persona ejecuta su propia copia del servidor en su equipo; no existe un servidor compartido. Sustituya `/RUTA` por la carpeta donde instaló el proyecto.

**Claude Desktop (verificado).** Cierre la aplicación por completo antes de editar el archivo `claude_desktop_config.json` y agregue la entrada; vuelva a abrirla después.

```json
{
  "mcpServers": {
    "colombia-datos": { "command": "/RUTA/.venv/bin/colombia-datos-mcp" }
  }
}
```

**Claude Code.**

```bash
claude mcp add colombia-datos -- /RUTA/.venv/bin/colombia-datos-mcp
```

**ChatGPT (uso avanzado, sin instalación de un clic).** Los servidores MCP personalizados de ChatGPT requieren una conexión por URL o por Secure MCP Tunnel; según la documentación de OpenAI consultada el 29 de octubre de 2026, la autenticación admitida es OAuth o ninguna, y la disponibilidad depende del plan y de los permisos del espacio de trabajo. Consulte la documentación vigente antes de configurarlo.

**Gemini CLI (pendiente de verificación).** La documentación del Gemini CLI describe la conexión de servidores MCP locales mediante su archivo de configuración. Esta configuración no ha sido probada en este proyecto; no se garantiza su funcionamiento con la aplicación web de Gemini.

**Servidor HTTP (solo para usuarios avanzados).**

```bash
colombia-datos-mcp --http --host 127.0.0.1 --port 8000
```

El modo HTTP no incluye autenticación. No lo exponga a internet sin añadir autenticación y límites de uso.

## Índice local de jurisprudencia y normas

```bash
colombia-datos-ingest ruta/a/carpeta_o_archivo.jsonl
```

Cada documento exige `titulo`, `texto`, `url_oficial` y `fecha_consulta`; sin ellos se rechaza. Recomendado: `corporacion`, `numero`, `radicado`, `fecha`, `ponente`, `tipo`. Si la búsqueda no arroja resultados, la herramienta indica: «No se encontró jurisprudencia oficial disponible.»

## Configuración pendiente

1. **Rama Judicial.** Endpoint de consulta por radicado verificado el 2026-10-29 (API interna del portal, puede cambiar sin aviso). Actuaciones verificadas el 2026-10-29; pendiente: documentos adjuntos y sujetos procesales.
2. **Probar en vivo** con `python prueba_en_vivo.py` tras cada cambio. Para incluir Rama Judicial, defina `RADICADO_PRUEBA` con un radicado público de 23 dígitos.

## Seguridad y privacidad

- No suba `.env` ni el índice local. El `.gitignore` incluido los excluye.
- Si usa un repositorio público, no incluya datos de clientes ni radicados de casos.
- Identidad, vehículos por propietario y antecedentes están fuera de alcance por tratarse de datos personales (ver arquitectura).

## Aviso legal

- Este proyecto no es una fuente oficial ni está afiliado a ninguna entidad pública. Consulta datos abiertos y portales públicos; la información debe contrastarse con la fuente oficial antes de usarla en un trámite o actuación.
- La consulta de la Rama Judicial utiliza una API interna del portal, no un servicio documentado; puede cambiar o dejar de funcionar sin aviso, y su uso debe respetar las condiciones del portal. Un resultado vacío no prueba que un proceso no exista.
- Una coincidencia de cribado OFAC es un indicio, no una determinación de identidad.
- El software se ofrece «tal cual», sin garantías (ver LICENSE). El usuario es responsable del uso que haga de los resultados y del cumplimiento de la normativa de protección de datos personales aplicable.

## Licencia

MIT. Ver el archivo `LICENSE`.
