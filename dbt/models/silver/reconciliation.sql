-- Reconciliación bronze = silver + rechazados, una fila por entidad (spec.md §6).
-- Ninguna fila de bronze se pierde sin explicación: o está en silver, o está en *_rejected.
-- El test assert_silver_reconciles_with_bronze exige difference = 0.
-- Es una tabla (no una vista): en Postgres, al reconstruir una tabla dbt hace drop ... cascade
-- y se llevaría una vista que dependa de ella si se reconstruye solo un modelo.

with counts as (
    select
        'trips' as entity,
        (select count(*) from {{ source('bronze', 'trips') }}) as bronze_rows,
        (select count(*) from {{ ref('trips') }}) as silver_rows,
        (select count(*) from {{ ref('trips_rejected') }}) as rejected_rows

    union all

    select
        'users' as entity,
        (select count(*) from {{ source('bronze', 'users_2024') }})
        + (select count(*) from {{ source('bronze', 'users_2025') }}) as bronze_rows,
        (select count(*) from {{ ref('users') }}) as silver_rows,
        (select count(*) from {{ ref('users_rejected') }}) as rejected_rows

    union all

    -- silver.stations suma las estaciones completadas desde los viajes (source = 'trips'):
    -- se reconcilian solo las del catálogo.
    select
        'stations' as entity,
        (select count(*) from {{ source('bronze', 'stations') }}) as bronze_rows,
        (
            select count(*)
            from {{ ref('stations') }}
            where source = 'catalog'
        ) as silver_rows,
        0 as rejected_rows

    union all

    select
        'comunas' as entity,
        (select count(*) from {{ source('bronze', 'comunas') }}) as bronze_rows,
        (select count(*) from {{ ref('comunas') }}) as silver_rows,
        0 as rejected_rows
)

select
    entity,
    bronze_rows,
    silver_rows,
    rejected_rows,
    bronze_rows - silver_rows - rejected_rows as difference,
    round(100.0 * rejected_rows / nullif(bronze_rows, 0), 4) as rejected_pct
from counts
