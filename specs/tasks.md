<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../docs/assets/fudo-logo-white.svg">
    <img src="../docs/assets/fudo-logo-black.svg" alt="Fudo" width="120">
  </picture>
</p>

# Tareas

> Documento SDD 3/3. Ejecución de [plan.md](plan.md) para cumplir [spec.md](spec.md).
>
> **Flujo por tarea**: implementar → resumen + cómo verificar → revisión → **el autor hace el commit** con el mensaje sugerido → siguiente tarea.
>
> Estado: `[ ]` pendiente · `[~]` en revisión · `[x]` commiteada

---

## Fase 0 — SDD + bootstrap
- [x] **T0.1** Documentos SDD (`specs/plan.md`, `specs/spec.md`, `specs/tasks.md`).
  - Aceptación: los tres documentos revisados y aprobados.
  - Commit: `docs(specs): add plan, spec and tasks`
- [x] **T0.2** Esqueleto del repo: `.gitignore` (`data/raw/*` salvo `.gitkeep`, `.env`, `target/`, `logs/`; `data/reference/` **sí** se versiona), `.env.example`, carpetas vacías con `.gitkeep`, `README.md` mínimo.
  - Aceptación: `git status` no muestra los CSV de `data/raw/` ni secretos; sí muestra `data/reference/comunas.geojson`.
  - Commit: `chore: bootstrap repository structure`
- [x] **T0.3** Tooling: `etl/pyproject.toml` (uv, dependencias y grupo dev con pytest, ruff, sqlfluff y pre-commit) + `uv.lock`, `ruff.toml` en la raíz (aplica a todo el Python del repo), `.sqlfluff` (postgres, templater jinja), `.pre-commit-config.yaml`.
  - Aceptación: `uv run --project etl pytest` y `uv run --project etl pre-commit run --all-files` pasan.
  - Commit: `chore: add linting and pre-commit tooling`

> Datos de entrada ya disponibles en `data/raw/` (CSV; el zip es una copia y no se usa) y `data/reference/comunas.geojson`.

## Fase 1 — Profiling de datos
> El profiling exploratorio ya se hizo y sus conclusiones están en `spec.md §2`, FR-07 y §7. Las tareas de esta fase lo dejan reproducible y documentado en el repo.

- [x] **T1.1** Script de profiling (`etl/src/profiling/profile.py`): por CSV → encoding/BOM, columnas, nulos, duplicados, min/max, valores distintos de categóricas, y cruces de claves (viajes↔estaciones, viajes↔usuarios, estaciones↔comunas).
  - Aceptación: corre local y genera un reporte en `docs/profiling/` con los mismos números que `spec.md §2`.
  - Commit: `feat(profiling): add dataset profiling script`
- [x] **T1.2** `docs/data-dictionary.md`: cada columna de cada archivo con nombre original, nombre normalizado, tipo destino, ejemplo y regla de limpieza.
  - Aceptación: todas las columnas documentadas y consistentes con FR-04/FR-07.
  - Commit: `docs: add data dictionary`
- [x] **T1.3** ADRs: `docs/adr/001-comuna-assignment.md` (PostGIS + respaldo por cercanía), `002-station-catalog.md` (actual vs viejo), `003-users-coverage.md` (altas 2024 + 2025, 49 % de cobertura, `has_profile`). El GeoJSON ya está en `data/reference/`.
  - Commit: `docs(adr): record data sourcing decisions`

## Fase 2 — Infra
- [x] **T2.1** `docker-compose.yml`: `postgres` con imagen `imresamu/postgis:16-3.5.3-bookworm` (variante multi-arquitectura de `postgis/postgis`, que solo publica amd64), `metabase` v0.64.2.7 + `metabase-db`; healthchecks, volúmenes y dependencias por `service_healthy`. Los servicios `etl` y `metabase-provision` se suman en T3.4 y T7.1, cuando existan sus imágenes.
  - Aceptación: `docker compose config` válido; postgres healthy.
  - Commit: `build(docker): add compose stack`
- [x] **T2.2** `sql/init/`: extensión `postgis`; schemas `bronze`, `silver`, `gold`; roles `etl` (escritura) y `bi_reader` (solo lectura en gold).
  - Commit: `feat(db): add init scripts for schemas and roles`
- [x] **T2.3** `Makefile`: `up`, `down`, `reset`, `ps`, `logs`, `psql`, `etl`, `dbt`, `sql`, `setup`, `test`, `lint`, `profile` (crea `.env` desde `.env.example`; los comandos de servicios futuros avisan en qué tarea llegan).
  - Aceptación: `make help` lista los targets.
  - Commit: `build: add Makefile entrypoints`

## Fase 3 — Bronze (Python)
- [x] **T3.1** `config.py` (settings por env, validados al arrancar, contraseña fuera del `repr`) y `log.py` (logging estructurado JSON/texto + `stage()` con duración por etapa).
  - Commit: `feat(etl): add config and logging`
- [x] **T3.2** `extract.py`: mapeo archivo → tabla bronze (`trips`, `users_2024`, `users_2025`, `stations`, `stations_legacy`, `comunas`), quitar BOM, normalizar headers a snake_case (FR-01b), hash SHA-256 por archivo.
  - Aceptación: tests de normalización (`ID Cliente` → `id_cliente`, `género` → `genero`, BOM).
  - Commit: `feat(etl): discover input files and normalize headers`
- [x] **T3.3** `load_bronze.py` + comando `ecobici-ingest` (`--force`, `--only`): crea tabla TEXT según header, `COPY` con columnas de metadatos, `bronze._column_mapping`, registro en `bronze._ingestion_log`, skip si el hash ya fue cargado; el GeoJSON se carga como una fila por comuna con la geometría en TEXT. (FR-01..03)
  - Aceptación: correr dos veces no duplica filas; conteos iguales a `spec.md §2`.
  - Commit: `feat(etl): load raw CSVs into bronze with COPY`
- [x] **T3.4** Tests pytest (detección de formato, idempotencia con Postgres de test) + Dockerfile del `etl` + entrypoint `ingest → dbt build` + servicio `etl` en `docker-compose.yml` (one-shot, depende de `postgres` healthy; `metabase` espera `service_completed_successfully`).
  - Commit: `test(etl): add ingestion tests and container entrypoint`

## Fase 4 — Silver (dbt)
- [x] **T4.1** Proyecto dbt: `dbt_project.yml`, `profiles.yml` por env, `packages.yml` + `package-lock.yml` (dbt_utils 1.4.1, metaplane/dbt_expectations 0.10.10), sources de bronze con tests de contrato, macro `generate_schema_name`, `dbt deps` en el build de la imagen.
  - Commit: `feat(dbt): scaffold dbt project and bronze sources`
- [x] **T4.2** Silver de comunas (`ST_GeomFromGeoJSON`, índice GiST) y de estaciones: catálogo actual + 6 estaciones derivadas de viajes, comuna por `ST_Contains` con respaldo por cercanía. (FR-05, FR-05b, FR-05c)
  - Aceptación: 413 estaciones (407 + 6); todas con comuna salvo la 510 sin ubicación (`unknown`); AEROPARQUE con `comuna_assignment = 'nearest'` y comuna 14 (ADR 001); toda estación de los viajes existe en silver.
  - Commit: `feat(dbt): add silver comunas and stations with spatial join`
- [x] **T4.3** Silver de usuarios: unión de `users_2024` y `users_2025` con esquema común (FR-01c), rejected, edad inválida → NULL, `fecha_alta` + `hora_alta` → timestamp.
  - Aceptación: 389.751 usuarios (197.077 + 192.674), `signup_year` en {2024, 2025}.
  - Commit: `feat(dbt): add silver users`
- [x] **T4.4** Silver de viajes con reglas FR-07 y rejected (FR-08): 3.155.783 válidos + 399 rechazados; test warn para los 8 viajes con fin = inicio.
  - Commit: `feat(dbt): add silver trips with quality rules`
- [x] **T4.5** Tests dbt de silver + reconciliación bronze = silver + rejected (`silver.reconciliation` + test `assert_silver_reconciles_with_bronze`).
  - Commit: `test(dbt): add silver data quality tests`

## Fase 5 — Gold (dbt) + análisis
- [x] **T5.1** Dimensiones: `dim_station` (413), `dim_comuna` (15), `dim_user` (487.262: usuarios de los viajes + de los archivos de alta, con `has_profile`), `dim_bike_model` (2), `dim_date` (732 días). (FR-09)
  - Commit: `feat(dbt): add gold dimensions`
- [x] **T5.2** `fct_trips` (3.155.783 viajes, con `start_date`, `start_hour`, `duration_minutes` y `distance_m` entre estaciones) + tests de relaciones con las 4 dimensiones.
  - Commit: `feat(dbt): add trips fact table`
- [x] **T5.3** `agg_station_od_monthly` (FR-10): 535.947 filas mes × origen × destino, con nombres, comunas y coordenadas de las dos estaciones; suma exacta contra `fct_trips` por mes.
  - Commit: `feat(dbt): add monthly origin-destination aggregate`
- [~] **T5.4** Marts Q1–Q6 en gold (FR-11): 8 marts en `models/gold/marts/` + test `assert_marts_reconcile` (los marts cuadran entre sí y con `fct_trips`).
  - Commit: `feat(dbt): add analytical marts for challenge questions`
- [ ] **T5.5** `sql/analysis/q1..q6_*.sql` + target `make sql` (FR-12).
  - Commit: `feat(sql): add standalone analysis queries`
- [ ] **T5.6** `dbt docs` + diagrama ER en `docs/er-diagram.md`.
  - Commit: `docs: add ER diagram and dbt docs`

## Fase 6 — Optimización SQL (extra)
- [ ] **T6.1** `EXPLAIN ANALYZE` baseline de Q1–Q6 y del OD → `sql/optimization/baseline.md`.
  - Commit: `perf(sql): capture query baselines`
- [ ] **T6.2** Índices (post-hooks dbt) y particionado mensual de `fct_trips` o agregados materializados; medición después.
  - Aceptación: mejora documentada antes/después. (EX-01)
  - Commit: `perf(db): add indexes and partitioning to gold`

## Fase 7 — Metabase
- [ ] **T7.1** `metabase/provision.py`: espera healthy, setup admin, conexión a Postgres con `bi_reader` + servicio `metabase-provision` en `docker-compose.yml` (one-shot, depende de `metabase` healthy).
  - Commit: `feat(metabase): automate setup and database connection`
- [ ] **T7.2** Preguntas y dashboard: OD entre estaciones con filtros mes/comuna, mapa, evolución mensual, Q1–Q6. (FR-14, EX-02)
  - Aceptación: dashboard visible en `localhost:3000` tras `make up`.
  - Commit: `feat(metabase): provision trips dashboard`

## Fase 8 — README y entrega
- [ ] **T8.1** README: requisitos, `make up`, arquitectura, modelo, decisiones/trade-offs, cómo probar, capturas, próximos pasos.
  - Commit: `docs: complete README`
- [ ] **T8.2** Validación final en clon limpio (`make reset && make up`) contra criterios de `spec.md §6`.
  - Commit: `chore: final validation fixes` (si aplica)

## Fase 9 — Opcional: big data y análisis avanzado
- [ ] **T9.1** DuckDB sobre los CSV/Parquet para análisis pesados o comparación de performance. (EX-03)
  - Commit: `feat(analytics): add DuckDB exploration`
- [ ] **T9.2** Módulo `analytics/` con scikit-learn: entrena los 3 modelos de EX-04, escribe `gold.ml_demand_predictions`, `gold.ml_coefficients`, `gold.ml_metrics` y `gold.ml_residuals`; se suma como paso opcional del servicio `etl` y agrega una pestaña "Modelos" al dashboard de Metabase. (EX-04)
  - Aceptación: tablas `ml_*` pobladas, métricas superan el baseline o se documenta por qué no, gráficos visibles en Metabase.
  - Commit: `feat(analytics): add scikit-learn models with results in Metabase`
