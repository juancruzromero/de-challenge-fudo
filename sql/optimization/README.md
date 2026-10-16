<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../../docs/assets/fudo-logo-white.svg">
    <img src="../../docs/assets/fudo-logo-black.svg" alt="Fudo" width="120">
  </picture>
</p>

# Optimización SQL

Mediciones antes y después de optimizar (EX-01). Se mide lo que importa en este proyecto:

- **Consultas:** las de Q1–Q6 (`sql/analysis/`) y las del dashboard (`dashboard.sql`), como `bi_reader`.
- **Build:** el tiempo de cada modelo de dbt, que es la mayor parte de `make up`.

## Cómo se mide

```bash
make bench label=baseline                    # dbt run + consultas → baseline.md
make bench label=after baseline=baseline     # lo mismo, comparado contra baseline
make bench label=x skip_dbt=1 only=q6        # solo consultas, filtradas por nombre
```

- **Repeticiones:** cada sentencia corre una vez para calentar la caché y después 5 veces con `EXPLAIN (ANALYZE, BUFFERS)`. Se informa la mediana.
- **Estadísticas:** el benchmark espera a que las tablas grandes de gold las tengan. dbt no las calcula, y sin ellas el planner estima a ciegas (ver hallazgo 1).
- **Entorno:** el Postgres del `docker compose` con la configuración por defecto de la imagen, en una laptop (Apple Silicon, Docker Desktop). Lo que vale son las diferencias relativas, no los milisegundos absolutos.

| Archivo | Qué es |
|---|---|
| [`dashboard.sql`](dashboard.sql) | Consultas representativas del dashboard (T7.2), con su nombre en `-- name:`. |
| [`baseline.md`](baseline.md) | Medición inicial: generada, no editar a mano. |
| `plans/<label>/` | Plan completo de cada consulta (`EXPLAIN ANALYZE` en texto), para comparar con diff. |
| `results/<label>.json` | Datos crudos de cada medición: el input de las comparaciones. |

## Línea de base (T6.1)

Resumen de [`baseline.md`](baseline.md):

| Qué | Tiempo | Comentario |
|---|--:|---|
| Build de dbt (`dbt run`) | 77 s | `trips` + `trips_rejected` 58 s, `stations` 20 s, `mart_q6` 13 s |
| Consultas del dashboard (sobre `agg_station_od_monthly`) | 1–215 ms | Todas cumplen NFR-07 (< 2 s) |
| Top OD de un mes **sin** el agregado (sobre `fct_trips`) | 577 ms | 47× más lenta que con el agregado (12 ms) |
| Q1–Q4 | 0,3–0,9 s | Escaneo completo de `fct_trips` (3,1 M filas) |
| Q5 | 2,5–2,9 s | Percentiles: ordenan 3,1 M filas, no se paralelizan |
| Q6 | **12,5 s** | La peor, por lejos |

## Diagnóstico

Hipótesis para T6.2, sacadas de los planes de `plans/baseline/`:

1. **Las tablas de dbt nacen sin estadísticas.** dbt crea cada tabla con `CREATE TABLE AS` y no ejecuta `ANALYZE`.
   - **Tablas grandes:** después de un build hubo que esperar **65 s** a que el autovacuum analizara `fct_trips` y `agg_station_od_monthly`.
   - **Tablas chicas:** los marts y `dim_bike_model` no llegan al umbral del autovacuum (50 filas + 10 %), así que no se analizan nunca.
   - **Consecuencia:** hasta entonces, Metabase consulta con estimaciones por defecto.
   - **Impacto medido hoy: bajo.** La primera medición, con Q1–Q5 todavía sin estadísticas, dio tiempos parecidos a la segunda. Estas consultas recorren la tabla completa y el plan casi no depende de las estimaciones. El riesgo está en las consultas con filtros, donde una mala estimación cambia el plan.
   - **Propuesta:** `analyze` como post-hook de cada tabla. Con eso, cada build deja el modelo listo para consultar.
2. **Q6: la agregación por usuario se calcula 3 veces y con lecturas aleatorias.** La agregación de 3,1 M viajes queda debajo de un `Hash` dentro de un `Gather`, y la arman por separado el proceso principal y los 2 workers (`loops=3`).
   - **Lectura aleatoria:** como `count(distinct)` y `mode()` piden entrada ordenada, el planner recorre `fct_trips` por el índice de `user_id`. La tabla no está ordenada por usuario, así que cada fila es una lectura aleatoria del heap.
   - **Costo:** 9,4 M de buffers (47 GB de caché y 25 GB de disco) para una tabla de 329 MB.
   - **Mismo patrón:** `mart_q6_top_users` lo repite en el build (13 s).
   - **Propuestas, a medir:** materializar la agregación por usuario, ordenar `fct_trips` físicamente, o reescribir para que agregue con un solo escaneo secuencial.
3. **`work_mem` de 4 MB: los ordenamientos van a disco.**
   - **Ordenamientos a disco** (`external merge`): Q3, Q4 y Q5 escriben de 55 a 266 MB a temporales, y el mapa de estaciones (`d4`) 33 MB.
   - **Hashes partidos:** se dividen en lotes (`Batches: 4`).
   - **Configuración:** el contenedor usa los valores de fábrica (`shared_buffers` 128 MB). La tabla de hechos sola ocupa 486 MB con índices.
   - **Propuesta:** subir `work_mem` y `shared_buffers` con `command:` en el compose, de forma acotada para una laptop.
4. **Silver: `trips_validated` se calcula dos veces.** Es efímero, así que `trips` (30 s) y `trips_rejected` (27 s) repiten cada uno la limpieza completa de bronze: regex sobre 3,1 M filas y una ventana para detectar duplicados.
   - **Propuesta:** materializarlo una sola vez. Es una tabla intermedia, y la regla "views solo sobre bronze" se respeta.
5. **`stations` (20 s) lee bronze.trips completo dos veces**, una por el origen y otra por el destino. Lo hace para encontrar 6 estaciones que faltan en el catálogo.
   - **Propuesta:** filtrar primero los ID que no están en el catálogo y recién después limpiar texto y coordenadas.
6. **Q5: los percentiles no se paralelizan.** Los agregados ordenados (`percentile_cont`) corren en un solo proceso: ordenan 3,1 M filas con 4 MB de `work_mem`.
   - **Plan:** recorre los 2 modelos por índice y repite el join contra una copia materializada de `fct_trips` (nested loop). Ya probé que no es un problema de estadísticas: con `dim_bike_model` analizada el plan es el mismo.
   - **Lo que se puede mejorar:** la memoria (punto 3) y la duración guardada como entero en minutos×100, para ordenar más barato. Hay que medir si alguno de los dos cambia algo.
7. **Sin margen en el dashboard.** Todas sus consultas leen el agregado y tardan como mucho 215 ms. El agregado ya es la optimización principal: 47× contra `fct_trips`.
   - **Particionado mensual de `fct_trips`:** con 3,1 M filas y consultas que recorren el año completo, no reduciría lo que se lee. Se evalúa en T6.2, pero la hipótesis es que no conviene.
