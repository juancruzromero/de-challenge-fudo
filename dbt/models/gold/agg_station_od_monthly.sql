{{
    config(
        indexes=[
            {'columns': ['month_start', 'origin_station_id', 'destination_station_id'], 'unique': true},
            {'columns': ['origin_station_id']},
            {'columns': ['destination_station_id']},
            {'columns': ['origin_comuna_label', 'destination_comuna_label']},
        ]
    )
}}

-- Volumen de viajes entre estaciones por mes (FR-10). Grano: mes × origen × destino.
-- Es la fuente del dashboard de volumen entre estaciones: trae los atributos de las dos
-- estaciones ya resueltos para que Metabase filtre y mapee sin tocar fct_trips (NFR-07).

with od as (
    select
        date_trunc('month', started_at)::date as month_start,
        origin_station_id,
        destination_station_id,
        count(*) as trips,
        round(avg(duration_minutes), 2) as avg_duration_minutes,
        round(
            (percentile_cont(0.5) within group (order by duration_minutes))::numeric, 2
        ) as median_duration_minutes,
        max(distance_m) as distance_m
    from {{ ref('fct_trips') }}
    group by
        date_trunc('month', started_at)::date,
        origin_station_id,
        destination_station_id
)

select
    od.month_start,
    to_char(od.month_start, 'YYYY-MM') as year_month,
    od.origin_station_id,
    origin.station_name as origin_station_name,
    origin.comuna as origin_comuna,
    origin.comuna_label as origin_comuna_label,
    origin.latitude as origin_latitude,
    origin.longitude as origin_longitude,
    od.destination_station_id,
    destination.station_name as destination_station_name,
    destination.comuna as destination_comuna,
    destination.comuna_label as destination_comuna_label,
    destination.latitude as destination_latitude,
    destination.longitude as destination_longitude,
    od.origin_station_id = od.destination_station_id as is_round_trip,
    od.trips,
    od.avg_duration_minutes,
    od.median_duration_minutes,
    od.distance_m
from od
inner join {{ ref('dim_station') }} as origin
    on od.origin_station_id = origin.station_id
inner join {{ ref('dim_station') }} as destination
    on od.destination_station_id = destination.station_id
