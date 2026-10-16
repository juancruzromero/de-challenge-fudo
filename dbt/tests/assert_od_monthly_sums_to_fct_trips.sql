-- FR-10: el agregado origen-destino suma exactamente los viajes de fct_trips, mes por mes.
-- El test falla si devuelve filas (meses donde los totales no coinciden).
with aggregated as (
    select
        month_start,
        sum(trips) as trips
    from {{ ref('agg_station_od_monthly') }}
    group by month_start
),

facts as (
    select
        date_trunc('month', started_at)::date as month_start,
        count(*) as trips
    from {{ ref('fct_trips') }}
    group by date_trunc('month', started_at)::date
)

select
    coalesce(aggregated.month_start, facts.month_start) as month_start,
    aggregated.trips as aggregated_trips,
    facts.trips as fact_trips
from aggregated
full outer join facts
    on aggregated.month_start = facts.month_start
where aggregated.trips is distinct from facts.trips
