{{ config(materialized='ephemeral') }}

-- Viajes con un reject_reason por fila (FR-07, FR-08). Las reglas se evalúan en orden y se
-- informa la primera que falla. No se materializa: lo leen trips y trips_rejected.

with ranked as (
    select
        trip.*,
        row_number() over (
            partition by trip.trip_id order by trip.source_row_number
        ) as trip_id_rank
    from {{ ref('stg_bronze__trips') }} as trip
),

stations as (
    select station_id from {{ ref('stations') }}
)

select
    ranked.trip_id,
    ranked.started_at,
    ranked.ended_at,
    ranked.duration_seconds,
    ranked.origin_station_id,
    ranked.destination_station_id,
    ranked.user_id,
    ranked.bike_model,
    ranked.gender,
    ranked.origin_station_id = ranked.destination_station_id as is_round_trip,
    ranked.source_file,
    ranked.source_row_number,
    case
        when ranked.trip_id is null then 'invalid_trip_id'
        when ranked.trip_id_rank > 1 then 'duplicate_trip_id'
        when ranked.started_at is null or ranked.ended_at is null then 'invalid_timestamp'
        when extract(year from ranked.started_at) <> {{ var('analysis_year') }}
            then 'out_of_period'
        when ranked.ended_at < ranked.started_at then 'destination_before_origin'
        when ranked.origin_station_id is null or ranked.destination_station_id is null
            then 'missing_station'
        when origin.station_id is null or destination.station_id is null
            then 'unknown_station'
        when
            ranked.duration_seconds is null
            or ranked.duration_seconds <> trunc(ranked.duration_seconds)
            then 'invalid_duration'
        when ranked.duration_seconds <= 0 then 'non_positive_duration'
        when ranked.duration_seconds > 86400 then 'duration_over_24h'
        when ranked.user_id is null then 'invalid_user_id'
        when ranked.bike_model is null then 'invalid_bike_model'
    end as reject_reason
from ranked
left join stations as origin
    on ranked.origin_station_id = origin.station_id
left join stations as destination
    on ranked.destination_station_id = destination.station_id
