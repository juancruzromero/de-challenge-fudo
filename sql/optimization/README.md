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
- **Estadísticas:** el benchmark espera a que las tablas grandes de gold las tengan antes de medir. Hasta T6.2, dbt no las calculaba (hallazgo 1).
- **Entorno:** el Postgres del `docker compose`, con la configuración por defecto de la imagen, en una laptop (Apple Silicon, Docker Desktop con 6 GB). Lo que vale son las diferencias relativas, no los milisegundos absolutos.
- **Costo de medir:** `EXPLAIN ANALYZE` cronometra cada nodo del plan y eso suma entre 20 y 30 % en Q5 y Q6. Por ejemplo, Q6 da 2,1 s en el benchmark y 1,7 s ejecutada directo. Antes y después se miden igual, así que la comparación vale.

| Archivo | Qué es |
|---|---|
| [`dashboard.sql`](dashboard.sql) | Consultas representativas del dashboard (T7.2), con su nombre en `-- name:`. |
| [`baseline.md`](baseline.md) · [`after.md`](after.md) | Medición inicial (T6.1) y final (T6.2): generadas, no editar a mano. |
| `plans/<label>/` | Plan completo de cada consulta (`EXPLAIN ANALYZE` en texto), para comparar con diff. |
| `results/<label>.json` | Datos crudos de cada medición: el input de las comparaciones. |

## Resultado

Detalle en [`after.md`](after.md). Los datos no cambian: comparé con `EXCEPT ALL` en los dos sentidos cada mart, `silver.stations`, los rechazados, la reconciliación, `dim_station`, `dim_user` y `agg_station_od_monthly`, y con conteo más hash `silver.trips` y `fct_trips`. Todo dio idéntico.

| Qué | Antes | Después | |
|---|--:|--:|--:|
| Build de dbt (`dbt run`, tiempo de pared) | 63,6 s | 45,2 s | **−29 %** |
| Q6, usuarios más activos | 11.468 ms | 2.107 ms | **5,4×** |
| Q6, buffers leídos | 9,4 M | 58 mil | **160× menos** |
| Q5, duración por tramo de distancia | 2.498 ms | 1.700 ms | 1,5× |
| Q1–Q4, Q5 por modelo, dashboard | | | ≈ igual (±10 %) |
| Espera a las estadísticas después del build | 55 s | 0 s | |

| Modelo de dbt | Antes | Después |
|---|--:|--:|
| `trips` + `trips_rejected` | 26,7 + 24,2 s | 24,6 s (`trips_validated`) + 2,9 + 0,4 s |
| `stations` | 15,7 s | 4,4 s |
| `mart_q6_top_users` | 11,5 s | 1,2 s (+ 3,7 s de `int_user_trips`, que comparten Q3, Q4 y Q6) |

## Qué se cambió

1. **`vacuum (analyze, parallel 0)` como post-hook** de cada tabla de silver y gold ([`dbt_project.yml`](../../dbt/dbt_project.yml)).
   - **Por qué `vacuum` y no solo `analyze`:** mi primera versión hacía solo `analyze`, y Q1/Q2 pasaron de `Index Only Scan` a `Seq Scan`, entre 5 y 20 % más lentas. Un index-only scan necesita el visibility map, y eso lo arma `VACUUM`, no `ANALYZE`. La medición base lo tenía porque había pasado el autovacuum.
   - **Por qué `transaction: false`:** `VACUUM` no puede correr dentro de una transacción.
   - **Por qué `parallel 0`:** el vacuum paralelo de índices pide memoria compartida, y en `fct_trips` superaba los 64 MB de `/dev/shm` que Docker da por defecto. El build fallaba. En una tabla recién creada no hay tuplas muertas, así que el paralelismo no aporta nada.
   - **Resultado:** cada build deja todas las tablas listas para consultar, incluidas las chicas, que el autovacuum nunca analizaba. En Q5 por tramo, `dim_bike_model` con estadísticas cambia el plan: 1,5×.
2. **Q6 sin `count(distinct)` ni `mode()`** ([`q6_usuarios_mas_activos.sql`](../analysis/q6_usuarios_mas_activos.sql)).
   - **Cómo:** agrega en dos pasos, primero usuario × día y después usuario. La estación favorita sale de un conteo con `distinct on`, solo para el top. Así la agregación son hashes sobre un escaneo secuencial.
   - **Resultado:** idéntico a la consulta original, con los mismos desempates.
3. **`int_user_trips` materializado y con la misma agregación en dos pasos** ([`int_user_trips.sql`](../../dbt/models/gold/marts/int_user_trips.sql)). Era efímero y cada mart de Q3, Q4 y Q6 lo recalculaba con el plan malo de Q6.
4. **`trips_validated` materializado una sola vez** como tabla `unlogged`: es intermedia y se reconstruye en cada build, así que no necesita WAL. Antes `trips` y `trips_rejected` repetían la limpieza completa de bronze.
5. **`stg_bronze__trip_stations` agrupa antes de limpiar.** Los 6,3 M extremos de viaje son solo 438 variantes distintas de estación. Se agrupan los valores crudos en un solo escaneo de bronze (origen y destino con `lateral values`), y la limpieza corre sobre esas pocas filas. `stations` bajó de 15,7 a 4,4 s.

## Qué se probó y se descartó

- **Reemplazar la ventana de duplicados de `trips_validated` por un `group by`: empeoró, de 24 a 38 s.**
  - **Primer problema:** la vista de staging se inlinea, así que cada mención de una columna en el `CASE` vuelve a ejecutar su regex.
  - **Segundo problema:** el hash de duplicados lo armaba cada worker por su cuenta.
  - La subconsulta con ventana original evita las dos cosas, porque no se puede aplanar.
- **Limpieza sin regex (`translate` en lugar de `~`): solo 15 % más rápida.**
  - **Dónde está el costo:** el 90 % de los 24 s de `trips_validated` es la limpieza, que corre en un solo proceso. Las regex de `clean_id` cuestan 3,2 s por columna y hay 4; las de `clean_timestamp`, 3,5 s y hay 2.
  - **Por qué se descartó:** la ganancia no justificaba cambiar macros ya probadas.
- **Abaratar el paralelismo (`parallel_setup_cost` y `parallel_tuple_cost` en 0) para ese modelo: sin cambio, 24,9 s.** La proyección con la limpieza sigue arriba del `Gather`.
- **Particionar `fct_trips` por mes: no conviene.** Lo probé con una copia particionada e indexada igual:

  | Consulta | `fct_trips` | Particionada |
  |---|--:|--:|
  | Top origen-destino de un mes | 93 ms | 89 ms |
  | Q1 (año completo) | 125 ms | 129 ms |
  | Viajes de un usuario | 0,23 ms | 0,39 ms |

  - **Consultas de un mes:** el índice por `start_date` ya lee solo ese mes, así que podar particiones no agrega nada.
  - **Consultas del año completo:** leen todas las particiones igual.
  - **Búsquedas por usuario:** empeoran, porque buscan en el índice de cada una de las 12 particiones.
  - **Cuándo convendría:** con varios años de datos, o para borrar o recargar meses enteros.
  - **Para el dashboard:** el agregado `agg_station_od_monthly` sigue siendo la optimización que más rinde, 42× contra `fct_trips` (11 ms contra 466 ms).
- **Configuración de memoria de Postgres** (`shared_buffers` y `work_mem`, con `command:` en el compose): quedó fuera de alcance por decisión del proyecto, que mantiene los valores de fábrica de la imagen.
  - **Lo que se gana sin tocarla:** Docker Desktop pasó de 2 a 6 GB, y eso solo bajó el build de 77 a 64 s (la base de esta comparación).
  - **Lo que queda pendiente:** Q3, Q4, Q5 y Q6 siguen escribiendo de 55 a 550 MB a temporales con `work_mem` de 4 MB. Es la mejora que más rinde si se habilita.
