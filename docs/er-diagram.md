<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/fudo-logo-white.svg">
    <img src="assets/fudo-logo-black.svg" alt="Fudo" width="120">
  </picture>
</p>

# Modelo de datos

El modelo analítico vive en el schema `gold` de PostgreSQL. Es un **modelo estrella**: una tabla de hechos con un viaje por fila y cinco dimensiones. Sobre él se construyen un agregado origen-destino para el dashboard y un mart por cada pregunta del challenge.

La documentación interactiva de cada modelo, columna y test, con el linaje completo, se genera con dbt: `make docs` y abrir http://localhost:8080.

## Modelo estrella (`gold`)

```mermaid
erDiagram
    fct_trips }o--|| dim_station : "origin_station_id"
    fct_trips }o--|| dim_station : "destination_station_id"
    fct_trips }o--|| dim_user : "user_id"
    fct_trips }o--|| dim_bike_model : "bike_model_id"
    fct_trips }o--|| dim_date : "start_date"
    dim_station }o--o| dim_comuna : "comuna"

    fct_trips {
        bigint trip_id PK
        timestamp started_at
        timestamp ended_at
        date start_date FK
        smallint start_hour
        bigint origin_station_id FK
        bigint destination_station_id FK
        bigint user_id FK
        smallint bike_model_id FK
        integer duration_seconds
        numeric duration_minutes
        numeric distance_m
        boolean is_round_trip
    }

    dim_station {
        bigint station_id PK
        integer station_number
        text station_name
        text address
        numeric latitude
        numeric longitude
        geometry geom
        smallint comuna FK
        text comuna_label
        text comuna_assignment
        text source
    }

    dim_comuna {
        smallint comuna PK
        text comuna_label
        text barrios
        numeric area_km2
        numeric perimeter_m
        geometry geom
    }

    dim_user {
        bigint user_id PK
        boolean has_profile
        text gender
        text gender_source
        smallint age
        text age_group
        timestamp signed_up_at
        date signup_date
        integer signup_year
        date signup_month
        boolean has_dni
    }

    dim_bike_model {
        smallint bike_model_id PK
        text bike_model
    }

    dim_date {
        date date_day PK
        smallint year
        smallint quarter
        smallint month
        text month_name
        text year_month
        date month_start
        smallint day_of_month
        smallint day_of_week
        text day_name
        boolean is_weekend
    }
```

| Tabla | Grano | Filas | Notas |
|---|---|---|---|
| `fct_trips` | viaje | 3.155.783 | Viajes 2025 válidos. `distance_m` es la distancia en línea recta entre estaciones, no el recorrido. |
| `dim_station` | estación | 413 | 407 del catálogo actual + 6 que solo aparecen en los viajes (ADR 002). La 510 no tiene ubicación (`comuna` NULL). |
| `dim_comuna` | comuna | 15 | Polígonos oficiales (ADR 001). |
| `dim_user` | usuario | 487.262 | Usuarios con viajes y usuarios con alta 2024-2025 aunque no hayan viajado. `has_profile` = tiene edad y fecha de alta (ADR 003). |
| `dim_bike_model` | modelo | 2 | FIT e ICONIC. |
| `dim_date` | día | 732 | Del 2024-01-01 (primera alta) al 2026-01-01 (último fin de viaje). |

Todas las claves foráneas tienen un test de `relationships` en dbt, y `fct_trips` tiene un test que exige las mismas filas que `silver.trips`: ningún viaje se pierde en los joins.

## Agregados y marts (`gold`)

| Tabla | Grano | Para qué |
|---|---|---|
| `agg_station_od_monthly` | mes × estación de origen × estación de destino | Volumen de viajes entre estaciones a lo largo del año (dashboard). Trae nombres, comunas y coordenadas de las dos estaciones. |
| `int_user_trips` | usuario | Viajes, duración y días activos de cada usuario de `dim_user` (incluye los de 0 viajes). Base de los marts de Q3, Q4 y Q6. |
| `mart_q1_comunas_origin` | comuna | Q1: comunas de las que más viajes parten. |
| `mart_q2_comunas_destination` | comuna | Q2: comunas que más viajes reciben. |
| `mart_q3_trips_by_age_group` | rango etario | Q3: viajes por edad. |
| `mart_q3_age_correlation` | universo de usuarios | Q3: correlación y regresión viajes ~ edad. |
| `mart_q4_trips_by_signup_month` | mes de alta | Q4: viajes por cohorte, normalizados por exposición. |
| `mart_q5_duration_by_bike_model` | modelo | Q5: duración por modelo. |
| `mart_q5_duration_by_model_and_distance` | tramo de distancia × modelo | Q5: control por distancia. |
| `mart_q6_top_users` | usuario (top 100) | Q6: usuarios más activos. |

## Linaje: de los archivos al dashboard

```mermaid
flowchart LR
    subgraph raw["data/"]
        f_comunas[comunas.geojson]
        f_stations[estaciones.csv]
        f_users[usuarios 2024 y 2025]
        f_trips[ecobici-datasets-2025.csv]
        f_legacy[estaciones-sistema-viejo.csv]
    end

    subgraph bronze["bronze · Python COPY"]
        b_comunas[comunas]
        b_stations[stations]
        b_users[users_2024 · users_2025]
        b_trips[trips]
        b_legacy[stations_legacy]
    end

    subgraph silver["silver · dbt"]
        s_comunas[comunas]
        s_stations[stations]
        s_users[users · users_rejected]
        s_trips[trips_validated →<br/>trips · trips_rejected]
        s_recon[reconciliation]
    end

    subgraph gold["gold · dbt"]
        g_dims[dim_station · dim_comuna<br/>dim_user · dim_bike_model · dim_date]
        g_fct[fct_trips]
        g_agg[agg_station_od_monthly]
        g_marts[mart_q1 … mart_q6]
    end

    f_comunas --> b_comunas --> s_comunas --> s_stations
    f_stations --> b_stations --> s_stations
    f_users --> b_users --> s_users
    f_trips --> b_trips --> s_trips
    f_legacy --> b_legacy
    b_trips -. 6 estaciones que faltan en el catálogo .-> s_stations
    s_stations --> s_trips

    s_users --> s_recon
    s_trips --> s_recon

    silver --> g_dims
    s_trips --> g_fct
    g_dims --> g_fct
    g_fct --> g_agg
    g_fct --> g_marts
    g_dims --> g_marts

    g_agg --> mb[(Metabase)]
    g_marts --> mb
    g_fct --> sql[sql/analysis]
```

- `bronze.stations_legacy` no sigue a silver: el catálogo viejo reutiliza IDs de otras estaciones (ADR 002).
- Las vistas de staging (`silver.stg_bronze__*`) tipan bronze. Son las únicas vistas del proyecto: silver y gold se materializan como tablas, porque dbt-postgres reemplaza tablas con `drop ... cascade` y se llevaría las vistas que dependen de ellas.
- `silver.trips_validated` es una tabla intermedia (`unlogged`): limpia los viajes una sola vez y de ahí salen los válidos y los rechazados (T6.2).
- Cada tabla de silver y gold se crea con `vacuum (analyze)` como post-hook, así queda lista para consultar al terminar el build (T6.2).
- `silver.reconciliation` controla que bronze = silver + rechazados en cada entidad.
- Metabase se conecta con `bi_reader`, que solo puede leer `gold`.
