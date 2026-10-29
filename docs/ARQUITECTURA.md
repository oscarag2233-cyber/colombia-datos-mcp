# Arquitectura: MCP propio de datos públicos de Colombia

Borrador técnico sujeto a verificación y revisión final por el abogado responsable.
Fecha de elaboración: 29 de octubre de 2026.

## 1. Qué hace el modelo de Croma (observado)

A partir del catálogo de herramientas de Croma disponible en esta sesión y de los esquemas de siete de ellas (`rama_judicial_cases_by_radicado`, `corte_constitucional_rulings_search`, `secop_contracts_search`, `rues_entity_by_nit`, `runt_vehicle_by_plate`, `ofac_sanctions_screen`, `create_monitor`), el patrón es el siguiente.

| Rasgo | Cómo lo resuelve Croma | Equivalente en este repositorio |
|---|---|---|
| Una herramienta por fuente y operación | Pares `*_search` (lista) y detalle (un registro) | `sources/<fuente>.py`, una función por operación |
| Esquema tipado con filtros | Validación por patrón (radicado de 20–25 dígitos, NIT, placa), paginación (`page`, `per_page`) | Validación en cada adaptador; `limite`, `pagina` |
| Vigencia declarada | Campo `as_of` en cada respuesta | `envelope.as_of` y `fetched_at` |
| Resultado vacío definitivo | `found: false` | `results: []` y nota explícita |
| Fuente nombrada | `(Source: …; Country: …)` | `envelope.source`, `dataset`, `url` |
| Vigilancia programada | `create_monitor` (consulta guardada que avisa por correo) | Fase 2 (ver 5) |
| Cobertura de datos personales | RUNT, Policía, Procuraduría, Registraduría, SIMIT | Excluida en esta fase (ver 3) |

Croma centraliza fuentes que, individualmente, son públicas pero heterogéneas (APIs abiertas, portales con JavaScript, portales con verificación humana). Su valor es la normalización y el mantenimiento. Replicarlo implica asumir ese mantenimiento.

## 2. Matriz de las once categorías solicitadas

Estado: **Listo** (código y pruebas), **Parcial** (código, falta configuración), **Fase 2** (diseño, sin código), **Excluido** (decisión de diseño).

| Categoría | Fuente abierta candidata | Estado | Observaciones |
|---|---|---|---|
| Procesos judiciales | Consulta Nacional Unificada (Rama Judicial); SAMAI para lo contencioso | Listo (consulta por radicado) | Endpoint interno del portal capturado y verificado el 29-oct-2026 (`/api/v2/Procesos/Consulta/NumeroRadicacion`, puede cambiar sin aviso). Actuaciones: `/api/v2/Proceso/Actuaciones/{idProceso}` verificado el mismo día; faltan documentos adjuntos. Si el portal exige CAPTCHA, no se evade. |
| Jurisprudencia | Relatorías oficiales (Corte Constitucional, Corte Suprema, Consejo de Estado) | Parcial | Índice local SQLite FTS5 con ingesta obligatoria de URL oficial y fecha de consulta. Faltan los cargadores por corporación. |
| Notificaciones | Estados electrónicos y publicaciones procesales | Fase 2 | Mismo enfoque de captura XHR usado para la consulta de procesos. |
| Empresas | Extracto abierto del RUES en datos.gov.co (`c82u-588k`, publicado por `serviciorues`); Supersociedades | Listo | ID y columnas verificados el 29-oct-2026; consulta por nombre y por NIT probada en vivo. Cuando `nit` viene vacío, se toma `numero_identificacion` solo si `clase_identificacion` = NIT. Se omiten cédulas de personas naturales y del representante legal. No incluye el certificado de existencia y representación (servicio pagado). El dataset de establecimientos (`nb3d-v3n7`) queda sin integrar. |
| Identidad | Registraduría, ADRES, RUAF | Excluido | Datos personales; ver 3. |
| Sanciones | OFAC (SDN y alias); sanciones SECOP; Procuraduría | Listo (OFAC) | OFAC con archivos públicos y cribado difuso. Sanciones SECOP: dataset por ubicar. Procuraduría: fase 2 sujeta al análisis de 3. |
| Vehículos | RUNT | Excluido | Exige placa y documento del propietario; datos personales. |
| Contratación pública | SECOP II en datos.gov.co (contratos y procesos) | Listo | Columnas verificadas contra el esquema vivo y filtros de texto, fechas y procesos probados en vivo (29-oct-2026). |
| Valores | Superfinanciera / SIMEV | Fase 2 | Ubicar datasets en datos.gov.co. |
| Gravámenes | Registro de garantías mobiliarias; limitaciones en RUNT | Fase 2 | Por investigar si existe acceso abierto; RUNT queda excluido por 3. |
| Leyes | SUIN-Juriscol, Secretaría del Senado, Diario Oficial | Fase 2 | Cargadores hacia el índice local, con control de vigencia y modificaciones. |

## 3. Límites deliberados

1. **Datos personales.** Identidad, vehículos por propietario y antecedentes son datos personales sujetos a la Ley 1581 de 2012 (régimen general de protección de datos; verificar texto y vigencia en SUIN-Juriscol antes de citar). Un MCP que consulta por cédula y se comparte con terceros crea un tratamiento que exige base legitimadora y finalidad. Se deja fuera hasta definir ese análisis.
2. **Verificación humana.** No se implementa elusión de CAPTCHA ni de controles anti-automatización. Si una fuente los exige, la herramienta devuelve el error.
3. **Procesos reservados.** No se consultan ni se infieren.
4. **Inferencia.** Ningún adaptador completa campos ausentes. Una coincidencia de cribado es un indicio, no una determinación.

## 4. Diseño

```
Cliente (Claude / ChatGPT)
        │  MCP (stdio local o HTTP remoto)
        ▼
server.py  ── herramientas de solo lectura (readOnlyHint)
        │
        ├─ sources/secop.py        → datos.gov.co (Socrata)
        ├─ sources/ofac.py         → archivos SDN/ALT (caché 24 h)
        ├─ sources/rues.py         → extracto abierto RUES (configurable)
        ├─ sources/rama_judicial.py→ API interna (configurable, sin default)
        └─ store.py                → SQLite FTS5 (jurisprudencia y normas)
```

Principios de diseño:

- **Trazabilidad por construcción.** `envelope()` obliga a declarar fuente, dataset, URL, fecha de consulta y si el endpoint está verificado.
- **Sin endpoints presumidos.** Donde la ruta no está confirmada (Rama Judicial, RUES) no hay valor por defecto; la herramienta explica qué falta.
- **Fuentes oficiales primero.** No se usan agregadores de terceros (por ejemplo, actores de scraping de pago) como fuente.
- **Índice local con rechazo.** `store.insertar` rechaza documentos sin `url_oficial` y `fecha_consulta`.

## 5. Hoja de ruta

1. ~~Validar en vivo SECOP, RUES y OFAC~~ (hecho el 29-oct-2026 con `prueba_en_vivo.py`).
2. ~~Capturar el endpoint de Rama Judicial~~ (hecho para consulta por radicado). Actuaciones capturadas y verificadas (29-oct-2026).
3. ~~Ubicar el dataset RUES abierto~~ (hecho: `c82u-588k`). Integrar `nb3d-v3n7` (establecimientos) si se necesita.
4. Cargadores de relatoría (Corte Constitucional primero) hacia el índice local.
5. Estados electrónicos y monitores (equivalente a `create_monitor`) con tareas programadas.
6. Autenticación del endpoint HTTP antes de exponerlo fuera de tu red.

## 6. Despliegue en Claude y ChatGPT

- **Claude Desktop o Claude Code (local):** transporte stdio, sin red expuesta.
- **Conectores remotos (Claude y ChatGPT):** requieren servir el MCP por HTTPS en una URL pública y, por seguridad, autenticación (token o OAuth). Los requisitos y planes que habilitan conectores personalizados cambian; confirme en la documentación vigente de cada plataforma.
- **Costo.** Las fuentes son gratuitas, pero el servidor remoto tiene costo de infraestructura y mantenimiento.

## Referencias

serviciorues. (2026). *Personas Naturales, Personas Jurídicas y Entidades Sin Animo de Lucro* [Conjunto de datos c82u-588k; metadatos]. Datos Abiertos Colombia. https://www.datos.gov.co/api/views/c82u-588k.json (consultado el 29 de octubre de 2026).

Departamento Administrativo de la Presidencia de la República [Colombia]. (2026). *SECOP II - Contratos Electrónicos* [Conjunto de datos jbjy-vk9h; metadatos]. Datos Abiertos Colombia. https://www.datos.gov.co/api/views/jbjy-vk9h.json (consultado el 29 de octubre de 2026).

Departamento Administrativo de la Presidencia de la República [Colombia]. (2026). *SECOP II - Procesos de Contratación* [Conjunto de datos p6dx-8zbt; metadatos]. Datos Abiertos Colombia. https://www.datos.gov.co/api/views/p6dx-8zbt.json (consultado el 29 de octubre de 2026).

Office of Foreign Assets Control. (s. f.). *Sanctions List Service*. U.S. Department of the Treasury. https://sanctionslist.ofac.treas.gov/Home/static/index.html

Rama Judicial. (s. f.). *Consulta Nacional Unificada de procesos*. https://consultaprocesos.ramajudicial.gov.co/procesos/Index

Ley 1581 de 2012. Por la cual se dictan disposiciones generales para la protección de datos personales. Colombia. (Texto y vigencia pendientes de verificación en SUIN-Juriscol).
