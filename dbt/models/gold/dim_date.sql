{{
    config(
        indexes=[
            {'columns': ['date_day'], 'unique': true},
        ]
    )
}}

-- Calendario desde la primera alta de usuario hasta el último fin de viaje, para que tanto
-- las fechas de alta (2024-2025) como los viajes que terminan en 2026 tengan su día.
-- Sin feriados: se pueden sumar como seed desde una fuente oficial.

with bounds as (
    select
        least(
            (select min(signup_date) from {{ ref('users') }}),
            (select min(started_at)::date from {{ ref('trips') }})
        ) as first_day,
        (select max(ended_at)::date from {{ ref('trips') }}) as last_day
),

days as (
    select generate_series(bounds.first_day, bounds.last_day, interval '1 day')::date as date_day
    from bounds
)

select
    date_day,
    extract(year from date_day)::smallint as year,
    extract(quarter from date_day)::smallint as quarter,
    extract(month from date_day)::smallint as month,
    (array[
        'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
        'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
    ])[extract(month from date_day)::int] as month_name,
    to_char(date_day, 'YYYY-MM') as year_month,
    date_trunc('month', date_day)::date as month_start,
    extract(day from date_day)::smallint as day_of_month,
    extract(isodow from date_day)::smallint as day_of_week,
    (array[
        'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'
    ])[extract(isodow from date_day)::int] as day_name,
    extract(isodow from date_day) in (6, 7) as is_weekend
from days
