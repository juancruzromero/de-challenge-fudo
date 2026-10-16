<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../docs/assets/fudo-logo-white.svg">
    <img src="../docs/assets/fudo-logo-black.svg" alt="Fudo" width="120">
  </picture>
</p>

# Especificación

> Documento SDD 2/3. Define el **qué** y los criterios de aceptación. Cada requerimiento tiene un ID que se referencia desde [tasks.md](tasks.md).

## 1. Alcance
**Incluye**: ingesta de los datasets de `data/raw/` (viajes, usuarios, estaciones) y de la referencia geográfica de comunas, modelo relacional en capas, limpieza, consultas analíticas, dashboard y documentación.

**No incluye**: ingesta incremental/streaming, scheduling, autenticación de usuarios finales, despliegue en la nube, usuarios dados de alta antes de 2024.

## 2. Datos de entrada
Perfilados sobre los archivos completos con `uv run --project etl ecobici-profile`. Reporte completo en [`docs/profiling/profile.md`](../docs/profiling/profile.md); detalle por columna en [`docs/data-dictionary.md`](../docs/data-dictionary.md).

| Archivo | Uso | Filas | Formato | Hallazgos |
|---|---|---|---|---|
| `data/raw/ecobici-datasets-2025.csv` | Viajes 2025 | 3.156.182 | UTF-8 sin BOM, `,`, comillas `"` | 17 columnas; IDs con sufijo `BAEcobici`; columna `género` con tilde; duración con separador de miles en el 48% de las filas (`"3,108"`); 0 IDs de viaje duplicados. |
| `data/raw/usuarios-ecobici-2025.csv` | Usuarios con alta en 2025 | 192.674 | UTF-8 sin BOM | Headers con espacios (`ID Cliente`, `Customer Has Dni (Yes / No)`); edades de -41 a 2.025; 17 con separador de miles (`"2,024"`), que en realidad son años. |
| `data/raw/usuarios-ecobici-2024.csv` | Usuarios con alta en 2024 | 197.077 | UTF-8 **con BOM** | Esquema distinto a 2025: `id_usuario` en vez de `ID Cliente` y **sin** columna de DNI; edades de 4 a 2021 (76 fuera de [15, 100]); sin vacíos ni IDs duplicados; ningún ID se repite con 2025. |
| `data/raw/estaciones.csv` | Catálogo de estaciones (sistema actual) | 407 | UTF-8 **con BOM** | `barrio`, `comuna` y `emplazamiento` vacíos en todas las filas; `numero_de_estacion` con 9 repetidos (no es clave). |
| `data/raw/estaciones-sistema-viejo.csv` | Catálogo del sistema anterior | 204 | UTF-8 | IDs `1.0`, `2.0`…; 4 IDs vacíos y 1 repetido; solo se carga en bronze por trazabilidad (ver FR-05b). |
| `data/reference/comunas.geojson` | Polígonos de las 15 comunas (versionado) | 15 | GeoJSON, CRS84 (lon/lat) | Fuente: data.buenosaires.gob.ar. SHA-256 `c128dadf…de062e`. |

`data/raw/ecobici-datasets-2025.zip` es una copia del CSV de viajes y **no se usa** en el pipeline.

### Cruces entre datasets
- **Viajes ↔ estaciones**: el ID del viaje sin sufijo (`146BAEcobici` → `146`) coincide con `estaciones.id` en 398 de 404 estaciones, que cubren el **99,8 %** de las salidas y llegadas. Faltan 6 IDs (591, 448, 593, 443, 510, 594), que no están en ninguno de los dos catálogos.
- **Viajes ↔ usuarios**: de los 286.322 usuarios de los viajes, 188.801 tienen perfil y cubren **1.547.521 viajes (49 %)**:

| Archivo de usuarios | Usuarios con viajes | Viajes cubiertos | Viajes por usuario |
|---|---|---|---|
| Altas 2025 | 140.533 | 860.741 (27,3 %) | 6,1 |
| Altas 2024 | 48.268 | 686.780 (21,8 %) | 14,2 |
| **Total** | **188.801** | **1.547.521 (49,0 %)** | 8,2 |

  El 51 % restante son viajes de usuarios dados de alta antes de 2024. Hay 52.141 usuarios dados de alta en 2025 sin viajes.
- **Estaciones ↔ comunas**: 406 de las 407 estaciones caen dentro de un polígono. AEROPARQUE (id 541) queda fuera porque está sobre la costa.

## 3. Requerimientos funcionales

### Ingesta (bronze)
- **FR-01** Leer los CSV de `data/raw/` y el GeoJSON de `data/reference/`, y cargarlos a tablas de `bronze` sin transformar valores (columnas TEXT; geometría como GeoJSON TEXT).
- **FR-01b** Los nombres de columna se normalizan a snake_case ASCII (`ID Cliente` → `id_cliente`, `género` → `genero`, `Customer Has Dni (Yes / No)` → `customer_has_dni_yes_no`); se quita el BOM. El mapeo nombre original → normalizado queda en `bronze._column_mapping`.
- **FR-01c** Cada archivo de usuarios se carga en su propia tabla bronze (`users_2024`, `users_2025`), respetando su esquema. La unificación es en silver: `id_cliente` / `id_usuario` → `user_id`; `has_dni` queda NULL para 2024; se agrega `signup_year`.
- **FR-02** Cada fila de bronze guarda `_source_file`, `_row_number` y `_loaded_at`.
- **FR-03** La ingesta es idempotente: re-ejecutarla con los mismos archivos no duplica filas (`bronze._ingestion_log` con el hash SHA-256 de cada archivo).

### Limpieza (silver)
- **FR-04** Tipar y normalizar:
  - IDs: quitar el sufijo `BAEcobici` y pasar a entero (`146BAEcobici` → `146`; `1.0` → `1`).
  - Duración: quitar el separador de miles y pasar a entero en segundos.
  - Fechas: `YYYY-MM-DD HH:MM:SS` → `timestamp`; `fecha_alta` + `hora_alta` → `timestamp` de alta.
  - Textos: trim, género en {`MALE`, `FEMALE`, `OTHER`, NULL}, modelo en {`FIT`, `ICONIC`}.
  - Coordenadas: `numeric` y punto PostGIS (SRID 4326).
- **FR-05** **Estaciones**: la fuente es `estaciones.csv`. Las 6 estaciones que aparecen en los viajes y no están en el catálogo se completan con el nombre, la dirección y las coordenadas más frecuentes en los viajes, con `source = 'trips'`. Si una de ellas no tiene coordenadas válidas en ningún viaje, se conserva con coordenadas y comuna `NULL` y `comuna_assignment = 'unknown'` (hoy, solo la 510 "[Valet] Galpón").
- **FR-05b** El catálogo del sistema viejo **no se usa** para el modelo: 26 de sus 135 IDs compartidos corresponden a otra ubicación a 200 m o más (por ejemplo, el id 131 es "Retiro III" en el viejo y "Hospital de Clínicas" en el actual, a 2,4 km; el 176 es "Pinzón" y "Parque Sarmiento I", a 15 km).
- **FR-05c** **Comuna**: se asigna con PostGIS mediante `ST_Contains(comuna.geom, station.geom)`. Si una estación no cae en ningún polígono, se le asigna la comuna más cercana (`ST_Distance`) con `comuna_assignment = 'nearest'`. No se asigna barrio: el GeoJSON solo lista los barrios de cada comuna, sin sus polígonos.
- **FR-06** Deduplicar viajes, usuarios y estaciones por su ID natural.
- **FR-07** Reglas de calidad:

| Entidad | Regla | Tratamiento | Casos detectados |
|---|---|---|---|
| Viaje | duración > 24 h (86.400 s) | rechazado (`duration_over_24h`) | 398 |
| Viaje | duración ≤ 0 | rechazado (`non_positive_duration`) | 0 |
| Viaje | fecha de origen fuera de 2025 | rechazado (`out_of_period`) | 0 |
| Viaje | fecha de destino < fecha de origen | rechazado (`destination_before_origin`) | 0 |
| Viaje | sin ID de estación de origen o destino | rechazado (`missing_station`) | 1 |
| Viaje | sin nombre o coordenadas de estación | se conserva; los atributos salen de `dim_station` | 18 orígenes / 29 destinos |
| Viaje | coordenadas de estación en 0 (fuera de CABA) | se conserva; los atributos salen de `dim_station`. Son todos de la estación 510 "[Valet] Galpón", que queda sin comuna (FR-05) | 176 destinos |
| Viaje | misma estación de origen y destino | se conserva con `is_round_trip = true` | 275.733 |
| Viaje | género vacío | género = NULL | 8.601 |
| Usuario | edad no numérica o fuera de [15, 100] | edad = NULL (el usuario se conserva) | 2025: 100 (5 menores de 15, 95 mayores de 100, de los cuales 17 con separador de miles) · 2024: 76 (6 + 70) |
| Usuario | mismo ID en 2024 y 2025 | se conserva el alta más antigua | 0 |
| Estación | nombre distinto para el mismo ID | se usa el nombre del catálogo | 2 IDs (307, 449) |

- **FR-08** Las filas rechazadas se guardan en `silver.<entidad>_rejected` con `reject_reason`.

### Modelo analítico (gold)
- **FR-09** Modelo estrella. Desde silver, las columnas van en inglés snake_case (ver [diccionario de datos](../docs/data-dictionary.md)):
  - `dim_station` (station_id, station_number, station_name, address, latitude, longitude, geom, comuna, comuna_assignment, source)
  - `dim_comuna` (comuna, barrios, perimeter_m, area_m2, geom)
  - `dim_user` (user_id, has_profile, gender, age, age_group, signed_up_at, signup_year, signup_month, has_dni). Incluye **todos** los usuarios que aparecen en los viajes. Para los que no están en ninguno de los archivos de usuarios, `has_profile = false`, la edad y la fecha de alta quedan NULL y el género se toma del más frecuente en sus viajes.
  - `dim_bike_model` (bike_model_id, bike_model)
  - `dim_date` (date, day_of_week, month, quarter, is_weekend, is_holiday opcional)
  - `fct_trips` (trip_id, started_at, ended_at, origin_station_id, destination_station_id, user_id, bike_model_id, duration_seconds, is_round_trip)
- **FR-10** `agg_station_od_monthly`: viajes y duración media por par origen→destino y mes.
- **FR-11** Marts / consultas para cada pregunta del challenge:

| ID | Pregunta | Salida mínima | Universo |
|---|---|---|---|
| Q1 | Comunas de las que más viajes parten | comuna, viajes, % del total, ranking | todos los viajes |
| Q2 | Comunas que más viajes reciben | comuna, viajes, % del total, ranking | todos los viajes |
| Q3 | Relación edad ↔ cantidad de viajes | rango etario, usuarios, viajes, viajes por usuario, `regr_slope`/`regr_r2` | usuarios con `has_profile` y edad válida (~49 % de los viajes) |
| Q4 | Relación cantidad de viajes ↔ fecha de alta | cohorte de alta (mes, 2024–2025), usuarios, viajes, viajes por usuario, días desde el alta, comparación 2024 vs 2025 | usuarios con `has_profile` |
| Q5 | Relación duración ↔ modelo de bicicleta | modelo, viajes, duración media, mediana, p90 | todos los viajes |
| Q6 | Usuarios más activos de 2025 | top N usuarios, viajes, duración total, estación más usada | todos los viajes |

  Q3 y Q4 informan en su salida la cobertura (viajes incluidos sobre el total).
- **FR-12** Cada consulta Q1–Q6 existe como archivo legible en `sql/analysis/qN_*.sql` contra `gold`.

### Visualización
- **FR-13** Metabase se conecta a Postgres (usuario de solo lectura sobre `gold`).
- **FR-14** Se provisiona automáticamente un dashboard con:
  - volumen de viajes entre estaciones a lo largo del año (top pares OD, matriz/heatmap, filtro por mes y comuna)
  - mapa de estaciones con volumen de salidas/llegadas
  - un gráfico por cada pregunta Q1–Q6
  - evolución mensual de viajes

## 4. Requerimientos no funcionales
- **NFR-01** `make up` levanta todo desde cero; el único paso manual es tener los CSV en `data/raw/`.
- **NFR-02** El pipeline completo (ingesta + dbt) corre en < 10 min en una laptop.
- **NFR-03** Sin credenciales hardcodeadas: todo por `.env` (`.env.example` versionado).
- **NFR-04** Logs estructurados con conteos por etapa (leídas, cargadas, rechazadas).
- **NFR-05** Tests: pytest para la ingesta; tests dbt (`unique`, `not_null`, `relationships`, `accepted_values`, rangos) en verde.
- **NFR-06** Lint: ruff (Python) y sqlfluff (SQL/dbt) sin errores.
- **NFR-07** Consultas del dashboard responden en < 2 s (leen agregados).

## 5. Extras
- **EX-01** Optimización SQL: índices en FKs y fechas, índice espacial GiST en geometrías, particionado mensual de `fct_trips` o agregados materializados, con `EXPLAIN ANALYZE` antes/después en `sql/optimization/`.
- **EX-02** Visualización avanzada: filtros interactivos, drill-down, mapa.
- **EX-03** (Opcional) Datos más grandes: DuckDB/Parquet para profiling o análisis pesados.
- **EX-04** (Opcional, último) Análisis más complejos con scikit-learn, leyendo de `gold` y escribiendo resultados en tablas `gold.ml_*` que consume Metabase (Metabase no ejecuta Python):
  - Demanda diaria ~ día de semana, mes, feriado → `ml_demand_predictions` (real vs predicho).
  - Viajes por usuario ~ edad, antigüedad, género (`PoissonRegressor`, solo `has_profile`) → `ml_coefficients`.
  - Duración ~ modelo de bici, distancia entre estaciones, hora → `ml_coefficients`.
  - Métricas por modelo (R², MAE, RMSE vs baseline de la media, train/test split) → `ml_metrics`.
  - Se documenta que son correlaciones, no causalidad.

## 6. Criterios de aceptación globales
- [ ] `make reset && make up` termina sin errores y es reproducible.
- [ ] `count(bronze) = count(silver) + count(rejected)` por entidad.
- [ ] `dbt build` sin tests fallidos.
- [ ] Todas las estaciones de `dim_station` tienen comuna.
- [ ] `sql/analysis/q1..q6` devuelven resultados coherentes.
- [ ] Dashboard accesible en `http://localhost:3000` sin configuración manual.
- [ ] README explica cómo correr, probar, las decisiones tomadas y las limitaciones de los datos.

## 7. Decisiones sobre los datos
| Pregunta | Decisión |
|---|---|
| ¿El dataset de estaciones trae comuna/barrio? | No (columnas vacías). Se calcula con PostGIS (FR-05c). |
| ¿Sistema viejo o actual? | Actual (`estaciones.csv`). El viejo solo queda en bronze (FR-05b). |
| ¿Formato de duración y fechas? ¿Encoding? | Duración en segundos con separador de miles; fechas ISO; UTF-8 (con BOM en `estaciones.csv` y `usuarios-ecobici-2024.csv`). |
| ¿Género: viajes o usuarios? | El archivo de usuarios es la fuente de verdad; para usuarios sin perfil, el más frecuente en sus viajes. |
| ¿Hay viajes de usuarios que no están en el archivo de usuarios? | Sí. Con solo las altas 2025 la cobertura era del 27 %; se sumó el archivo de altas 2024 y llega al 49 %. El resto (altas anteriores a 2024) queda sin perfil y se documenta; Q3/Q4 se calculan sobre usuarios con perfil. |
| ¿Zip o CSV? | CSV; el zip es una copia y no se usa. |
