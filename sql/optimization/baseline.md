# Benchmark: baseline

> Generado por `make bench label=baseline`. No editar a mano: volver a correr el comando.

- Fecha: 2026-10-16 01:43
- PostgreSQL 16.10 (Debian 16.10-1.pgdg12+1)
- Corridas por consulta: 5 (más una de calentamiento); se informa la mediana del tiempo de ejecución de `EXPLAIN ANALYZE`.
- Configuración: `shared_buffers=128MB`, `work_mem=4MB`, `effective_cache_size=4GB`, `max_parallel_workers_per_gather=2`, `jit=on`, `random_page_cost=4`
- Estadísticas de gold: hubo que esperar 55 s al autoanalyze antes de medir.

## Consultas

| Consulta | Mediana (ms) | Mín–máx (ms) | Caché (MB) | Leído de disco (MB) | Temp escrito (MB) | Workers | Escaneos |
|---|--:|--:|--:|--:|--:|--:|---|
| `q1_comunas_origen` | 268 | 263–286 | 35,6 | 0 | 0 | 2 | Index Only Scan fct_trips<br>Seq Scan dim_station |
| `q2_comunas_destino` | 550 | 543–754 | 71,2 | 0 | 0 | 2 | Index Only Scan fct_trips<br>Seq Scan dim_station |
| `q3_edad_vs_viajes_1` | 795 | 765–880 | 86,1 | 283,7 | 55,6 | 2 | Seq Scan fct_trips<br>Seq Scan dim_user |
| `q3_edad_vs_viajes_2` | 704 | 639–763 | 96,5 | 273,2 | 55,6 | 2 | Seq Scan fct_trips<br>Seq Scan dim_user |
| `q4_fecha_alta_vs_viajes_1` | 819 | 763–904 | 107,1 | 262,7 | 188,2 | 2 | Seq Scan fct_trips<br>Seq Scan dim_user |
| `q4_fecha_alta_vs_viajes_2` | 746 | 708–759 | 117,6 | 252,2 | 55,6 | 2 | Seq Scan fct_trips<br>Seq Scan dim_user |
| `q5_duracion_vs_modelo_1` | 2.283 | 2.244–2.591 | 99,7 | 229,3 | 156,9 | 0 | Index Scan dim_bike_model<br>Seq Scan fct_trips |
| `q5_duracion_vs_modelo_2` | 2.498 | 2.426–2.530 | 104,9 | 225,0 | 266,4 | 2 | Seq Scan fct_trips<br>Index Scan dim_bike_model |
| `q6_usuarios_mas_activos` | 11.468 | 9.231–12.065 | 47.812,3 | 25.745,1 | 88,7 | 2 | Seq Scan dim_user<br>Index Scan fct_trips<br>Seq Scan dim_station |
| `d1_top_od_month` | 11,1 | 10,9–11,7 | 10,9 | 0 | 0 | 0 | Bitmap Heap Scan agg_station_od_monthly |
| `d1_top_od_month_from_fct` | 466 | 462–468 | 32,6 | 0 | 13,0 | 0 | Bitmap Heap Scan fct_trips<br>Seq Scan dim_station |
| `d2_top_od_by_comuna` | 26,5 | 26,3–27,1 | 18,9 | 0 | 0 | 0 | Bitmap Heap Scan agg_station_od_monthly |
| `d3_monthly_trend` | 43,1 | 43,0–46,6 | 29,6 | 71,5 | 0 | 2 | Seq Scan agg_station_od_monthly |
| `d4_station_map` | 182 | 180–191 | 35,8 | 66,3 | 33,4 | 2 | Seq Scan agg_station_od_monthly |
| `d5_comuna_matrix` | 52,0 | 51,7–52,2 | 40,1 | 61,0 | 0 | 2 | Seq Scan agg_station_od_monthly |
| `d6_station_drilldown` | 1,0 | 1,0–1,0 | 0,6 | 0 | 0 | 0 | Bitmap Heap Scan agg_station_od_monthly |

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

Tiempo total de pared: **63,6 s** (los modelos corren en paralelo).

| Modelo | Tiempo (s) |
|---|--:|
| `trips` | 26,7 |
| `trips_rejected` | 24,2 |
| `stations` | 15,7 |
| `mart_q6_top_users` | 11,5 |
| `fct_trips` | 5,9 |
| `agg_station_od_monthly` | 5,5 |
| `mart_q5_duration_by_bike_model` | 2,7 |
| `dim_user` | 2,6 |
| `mart_q5_duration_by_model_and_distance` | 2,2 |
| `mart_q3_age_correlation` | 1,4 |
| `mart_q3_trips_by_age_group` | 1,3 |
| `mart_q4_trips_by_signup_month` | 1,3 |
| `users` | 1,2 |

Se omiten los modelos de menos de 1 s.
