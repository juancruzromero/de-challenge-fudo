{{
    config(
        indexes=[
            {'columns': ['trip_id'], 'unique': true},
            {'columns': ['start_date']},
            {'columns': ['origin_station_id']},
            {'columns': ['destination_station_id']},
            {'columns': ['user_id']},
        ]
    )
}}

-- Un viaje de 2025 por fila (FR-09). Grano: viaje.
-- distance_m es la distancia en línea recta entre estaciones (no el recorrido real); NULL si
-- alguna estación no tiene ubicación (510).
select
    trip.trip_id,
    trip.started_at,
    trip.ended_at,
    trip.started_at::date as start_date,
    extract(hour from trip.started_at)::smallint as start_hour,
    trip.origin_station_id,
    trip.destination_station_id,
    trip.user_id,
    bike_model.bike_model_id,
    trip.duration_seconds,
    round(trip.duration_seconds / 60.0, 2) as duration_minutes,
    round(st_distancesphere(origin.geom, destination.geom)::numeric, 0) as distance_m,
    trip.is_round_trip
from {{ ref('trips') }} as trip
inner join {{ ref('dim_bike_model') }} as bike_model
    on trip.bike_model = bike_model.bike_model
inner join {{ ref('dim_station') }} as origin
    on trip.origin_station_id = origin.station_id
inner join {{ ref('dim_station') }} as destination
    on trip.destination_station_id = destination.station_id
