<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../docs/assets/fudo-logo-white.svg">
    <img src="../docs/assets/fudo-logo-black.svg" alt="Fudo" width="120">
  </picture>
</p>

# Plan técnico

> Documento SDD 1/3. Define el **cómo** a alto nivel. El **qué** está en [spec.md](spec.md) y la ejecución en [tasks.md](tasks.md).

## 1. Contexto
Challenge técnico de Data Engineer ([CHALLENGUE.md](../CHALLENGUE.md)): construir una base relacional alimentada por un ETL con los datos de viajes, usuarios y estaciones de Ecobici (Buenos Aires, 2025), visualizar el volumen de viajes entre estaciones y responder preguntas de negocio con SQL.

## 2. Objetivos
- Despliegue con **un solo comando** (`make up`), reproducible en cualquier máquina con Docker.
- Arquitectura **medallion** (bronze → silver → gold) con prácticas de mercado: idempotencia, tests de calidad de datos, lineage, documentación, configuración por variables de entorno.
- Código y SQL legibles para ser revisados en una entrevista.

## 3. Stack
| Capa | Herramienta | Motivo |
|---|---|---|
| Lenguaje ETL | Python 3.12 + `uv` | Gestión de dependencias rápida y reproducible (`uv.lock`). |
| Carga | `psycopg` 3 con `COPY` | Carga masiva de millones de filas en segundos. |
| Base de datos | PostgreSQL 16 + PostGIS 3.5 (`imresamu/postgis`, multi-arquitectura) | Relacional, estándar, particionado declarativo e índices avanzados; PostGIS asigna la comuna de cada estación por punto en polígono. |
| Transformación | dbt-core + dbt-postgres | Modelos SQL versionados, tests, docs y lineage. |
| Visualización | Metabase | Se conecta a Postgres, dashboards interactivos, provisionable por API. |
| Infra | Docker Compose + Makefile | Un comando, sin orquestador (batch anual, no lo justifica). |
| Calidad de código | ruff, sqlfluff, pytest, pre-commit | Lint y tests consistentes. |
| Análisis avanzado (opcional) | DuckDB · scikit-learn | Datos más grandes (DuckDB/Parquet) y modelos de regresión cuyos resultados se escriben en `gold.ml_*` para Metabase. |

## 4. Arquitectura

```
data/raw/*.csv (viajes, usuarios, estaciones)  +  data/reference/comunas.geojson
        │  etl (Python): quitar BOM → normalizar headers → COPY
        ▼
┌─────────── PostgreSQL ────────────────────────────────────────────┐
│ bronze   CSV crudo, todas las columnas TEXT + metadatos de carga  │
│          (_source_file, _row_number, _loaded_at), _ingestion_log  │
│    │ dbt                                                          │
│    ▼                                                              │
│ silver   tipado, normalizado, deduplicado; *_rejected con motivo  │
│    │ dbt                                                          │
│    ▼                                                              │
│ gold     modelo estrella + agregados + marts analíticos           │
└───────────────────────────────────────────────────────────────────┘
        │
        ▼
Metabase (dashboard provisionado por API)   ·   sql/analysis/*.sql
        ▲
        │ (opcional) analytics/ (scikit-learn) lee gold → escribe gold.ml_*
```

### Flujo de `make up`
1. `postgres` arranca y pasa el healthcheck; `sql/init` crea schemas y roles.
2. `etl` (one-shot): ingesta a bronze → `dbt build` (modelos + tests) → termina con código 0.
3. `metabase` arranca; `metabase-provision` (one-shot) crea la conexión, preguntas y dashboard.

### Decisiones clave
- **Bronze en Postgres como TEXT**: nunca falla por tipos; la limpieza es explícita, testeable y auditable en silver.
- **Rechazos, no descartes silenciosos**: cada fila filtrada en silver queda en `*_rejected` con `reject_reason`.
- **Idempotencia**: la ingesta registra el hash de cada archivo en `bronze._ingestion_log`; re-ejecutar no duplica datos. dbt reconstruye silver/gold de forma determinística.
- **Catálogo de estaciones actual**: `estaciones.csv` cruza con el 99,8 % de los viajes; el del sistema viejo reutiliza IDs para otras ubicaciones, así que solo queda en bronze.
- **Comuna con PostGIS**: `ST_Contains` contra los polígonos oficiales, con la comuna más cercana como respaldo (AEROPARQUE). El GeoJSON se versiona en `data/reference/` para que el pipeline no dependa de internet.
- **Usuarios sin perfil incluidos**: `dim_user` tiene a todos los usuarios de los viajes, con `has_profile` para distinguir a los que tienen edad y fecha de alta (altas 2024 y 2025, 49 % de los viajes). Así las FKs se mantienen y la limitación queda explícita en Q3/Q4.
- **Vistas solo sobre bronze; silver y gold como tablas**: en Postgres, al reconstruir una tabla dbt hace `drop ... cascade` y se lleva las vistas que dependen de ella. Las vistas de staging dependen de bronze, que la ingesta vacía con `truncate` (no `drop`), así que no se rompen; todo lo demás se materializa como tabla.
- **Gold orientado a consumo**: el dashboard lee de agregados (`agg_station_od_monthly`), no de la tabla de hechos completa.
- **ML desacoplado de la visualización**: Metabase no ejecuta Python; los modelos de scikit-learn escriben predicciones, coeficientes y métricas en tablas `gold.ml_*` que Metabase grafica como cualquier otra tabla.
- **Credenciales por `.env`** (con `.env.example` versionado), nunca hardcodeadas.

## 5. Estructura del repo
```
specs/        plan.md · spec.md · tasks.md
etl/          pyproject.toml · Dockerfile · src/ingest/ · tests/
dbt/          dbt_project.yml · profiles.yml · models/{staging,silver,gold} · tests/ · macros/ · seeds/
sql/          init/ · analysis/ · optimization/
metabase/     provision.py · Dockerfile
analytics/    (opcional) modelos scikit-learn → gold.ml_*
docs/         data-dictionary.md · adr/ · er-diagram.md · assets/ (logos)
data/raw/       (gitignored) CSV de entrada
data/reference/ (versionado) comunas.geojson
docker-compose.yml · Makefile · .env.example · README.md
```

## 6. Fases
| Fase | Entregable |
|---|---|
| 0 | SDD + bootstrap del repo |
| 1 | Profiling de datos → data dictionary y reglas de limpieza |
| 2 | Infra Docker + Makefile |
| 3 | Bronze (ingesta Python) |
| 4 | Silver (dbt) |
| 5 | Gold (dbt) + consultas de análisis |
| 6 | Optimización SQL (extra) |
| 7 | Metabase provisionado |
| 8 | README y entrega |
| 9 | (Opcional) DuckDB/Parquet para datos más grandes + scikit-learn para análisis avanzado (al final) |

## 7. Flujo de trabajo
- Cada tarea de [tasks.md](tasks.md) se implementa de a una.
- Al terminar una tarea: resumen de cambios + cómo verificar → **revisión del autor → el autor hace el commit** (Conventional Commits, mensaje sugerido en cada tarea).
- Si una tarea cambia el alcance, primero se actualiza `spec.md`/`tasks.md`.

## 8. Riesgos
| Riesgo | Mitigación |
|---|---|
| Estaciones sin comuna (confirmado) | PostGIS + GeoJSON oficial versionado; respaldo por comuna más cercana. |
| Usuarios solo con alta 2024–2025 (49 % de los viajes) | `has_profile` en `dim_user`; Q3/Q4 informan su cobertura; limitación documentada en el README. |
| Formatos sucios (duración con separador de miles, edades inválidas, BOM, headers con espacios) | Normalización en la ingesta (headers, BOM) y parseo defensivo en silver con rechazos. |
| Volumen (3,16 M viajes, 830 MB) | `COPY`, índices después de cargar, agregados materializados para el dashboard. |
| Provisionar Metabase sin clicks | Script contra la API REST con reintentos hasta que Metabase esté healthy. |
