# Benchmark: baseline

> Generado por `make bench label=baseline`. No editar a mano: volver a correr el comando.

- Fecha: 2026-10-16 01:22
- PostgreSQL 16.10 (Debian 16.10-1.pgdg12+1)
- Corridas por consulta: 5 (más una de calentamiento); se informa la mediana del tiempo de ejecución de `EXPLAIN ANALYZE`.
- Configuración: `shared_buffers=128MB`, `work_mem=4MB`, `effective_cache_size=4GB`, `max_parallel_workers_per_gather=2`, `jit=on`, `random_page_cost=4`
- Estadísticas de gold: hubo que esperar 65 s al autoanalyze antes de medir.

## Consultas

| Consulta | Mediana (ms) | Mín–máx (ms) | Caché (MB) | Leído de disco (MB) | Temp escrito (MB) | Workers | Escaneos |
|---|--:|--:|--:|--:|--:|--:|---|
| `q1_comunas_origen` | 327 | 322–332 | 35,7 | 0 | 0 | 2 | Index Only Scan fct_trips<br>Seq Scan dim_station |
| `q2_comunas_destino` | 656 | 633–722 | 71,5 | 0 | 0 | 2 | Index Only Scan fct_trips<br>Seq Scan dim_station |
| `q3_edad_vs_viajes_1` | 923 | 860–1.092 | 85,9 | 283,9 | 55,6 | 2 | Seq Scan fct_trips<br>Seq Scan dim_user |
| `q3_edad_vs_viajes_2` | 777 | 767–842 | 96,2 | 273,4 | 55,6 | 2 | Seq Scan fct_trips<br>Seq Scan dim_user |
| `q4_fecha_alta_vs_viajes_1` | 916 | 905–978 | 106,9 | 262,9 | 188,1 | 2 | Seq Scan fct_trips<br>Seq Scan dim_user |
| `q4_fecha_alta_vs_viajes_2` | 805 | 761–959 | 117,4 | 252,4 | 55,6 | 2 | Seq Scan fct_trips<br>Seq Scan dim_user |
| `q5_duracion_vs_modelo_1` | 2.484 | 2.483–2.594 | 100,1 | 228,9 | 156,9 | 0 | Index Scan dim_bike_model<br>Seq Scan fct_trips |
| `q5_duracion_vs_modelo_2` | 2.909 | 2.821–3.258 | 105,2 | 224,7 | 266,3 | 2 | Seq Scan fct_trips<br>Index Scan dim_bike_model |
| `q6_usuarios_mas_activos` | 12.483 | 10.729–12.882 | 47.673,7 | 25.868,4 | 88,7 | 2 | Seq Scan dim_user<br>Index Scan fct_trips<br>Seq Scan dim_station |
| `d1_top_od_month` | 12,2 | 11,6–12,6 | 10,9 | 0 | 0 | 0 | Bitmap Heap Scan agg_station_od_monthly |
| `d1_top_od_month_from_fct` | 577 | 566–590 | 32,5 | 0 | 13,0 | 0 | Bitmap Heap Scan fct_trips<br>Seq Scan dim_station |
| `d2_top_od_by_comuna` | 32,4 | 32,1–33,9 | 18,9 | 0 | 0 | 0 | Bitmap Heap Scan agg_station_od_monthly |
| `d3_monthly_trend` | 49,1 | 47,8–50,7 | 29,6 | 71,5 | 0 | 2 | Seq Scan agg_station_od_monthly |
| `d4_station_map` | 215 | 211–222 | 35,8 | 66,3 | 33,4 | 2 | Seq Scan agg_station_od_monthly |
| `d5_comuna_matrix` | 65,4 | 65,0–66,1 | 40,1 | 61,0 | 0 | 2 | Seq Scan agg_station_od_monthly |
| `d6_station_drilldown` | 1,0 | 1,0–1,1 | 0,6 | 0 | 0 | 0 | Bitmap Heap Scan agg_station_od_monthly |

<details><summary>Qué mide cada consulta</summary>

- `q1_comunas_origen` (sql/analysis/q1_comunas_origen.sql): Q1: ¿De qué comunas parten más viajes?
- `q2_comunas_destino` (sql/analysis/q2_comunas_destino.sql): Q2: ¿Qué comunas reciben más viajes?
- `q3_edad_vs_viajes_1` (sql/analysis/q3_edad_vs_viajes.sql): Q3: ¿Qué relación hay entre la edad de los usuarios y la cantidad de viajes que hicieron?
- `q3_edad_vs_viajes_2` (sql/analysis/q3_edad_vs_viajes.sql): 2. Correlación y regresión lineal simple viajes ~ edad, a nivel usuario.
- `q4_fecha_alta_vs_viajes_1` (sql/analysis/q4_fecha_alta_vs_viajes.sql): Q4: ¿Qué relación hay entre la cantidad de viajes y la fecha de alta de los usuarios?
- `q4_fecha_alta_vs_viajes_2` (sql/analysis/q4_fecha_alta_vs_viajes.sql): Resumen por año de alta: las altas 2025 siguen activas mucho más que las de 2024.
- `q5_duracion_vs_modelo_1` (sql/analysis/q5_duracion_vs_modelo.sql): Q5: ¿Qué relación hay entre la duración de los viajes y el modelo de bicicleta?
- `q5_duracion_vs_modelo_2` (sql/analysis/q5_duracion_vs_modelo.sql): 2. Control por distancia: la misma comparación dentro de cada tramo de distancia en línea
- `q6_usuarios_mas_activos` (sql/analysis/q6_usuarios_mas_activos.sql): Q6: ¿Quiénes fueron los usuarios más activos durante 2025?
- `d1_top_od_month` (sql/optimization/dashboard.sql): Consultas representativas del dashboard de Metabase (T7.2), para medir con make bench.
- `d1_top_od_month_from_fct` (sql/optimization/dashboard.sql): La misma consulta sin el agregado, directo sobre fct_trips: lo que costaría sin
- `d2_top_od_by_comuna` (sql/optimization/dashboard.sql): Top 20 recorridos del año que salen de una comuna (filtro de comuna del dashboard).
- `d3_monthly_trend` (sql/optimization/dashboard.sql): Evolución mensual de viajes (serie de tiempo del dashboard).
- `d4_station_map` (sql/optimization/dashboard.sql): Viajes que salen de cada estación en el año, con coordenadas (mapa de estaciones).
- `d5_comuna_matrix` (sql/optimization/dashboard.sql): Matriz comuna de origen × comuna de destino en el año.
- `d6_station_drilldown` (sql/optimization/dashboard.sql): Destinos de una estación, mes a mes (detalle de una estación).

</details>

## Build de dbt (`dbt run`)

Tiempo total de pared: **77,3 s** (los modelos corren en paralelo).

| Modelo | Tiempo (s) |
|---|--:|
| `trips` | 30,5 |
| `trips_rejected` | 27,5 |
| `stations` | 20,5 |
| `mart_q6_top_users` | 13,1 |
| `fct_trips` | 7,7 |
| `agg_station_od_monthly` | 7,2 |
| `dim_user` | 4,4 |
| `reconciliation` | 3,6 |
| `mart_q5_duration_by_bike_model` | 3,5 |
| `mart_q5_duration_by_model_and_distance` | 3,3 |
| `mart_q3_trips_by_age_group` | 2,5 |
| `users` | 2,2 |
| `mart_q4_trips_by_signup_month` | 2,1 |
| `dim_date` | 2,1 |
| `mart_q3_age_correlation` | 2,0 |
| `users_rejected` | 1,6 |
| `mart_q2_comunas_destination` | 1,1 |
| `mart_q1_comunas_origin` | 1,1 |

Se omiten los modelos de menos de 1 s.
