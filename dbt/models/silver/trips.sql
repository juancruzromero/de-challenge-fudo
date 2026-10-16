{{
    config(
        indexes=[
            {'columns': ['trip_id'], 'unique': true},
        ]
    )
}}

-- Viajes 2025 que pasan todas las reglas de calidad (FR-07). El resto va a trips_rejected.
select
    trip_id,
    started_at,
    ended_at,
    duration_seconds::integer as duration_seconds,
    origin_station_id,
    destination_station_id,
    user_id,
    bike_model,
    gender,
    is_round_trip
from {{ ref('trips_validated') }}
where reject_reason is null
