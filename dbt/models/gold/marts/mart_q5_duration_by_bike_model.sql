-- Q5: relación entre la duración de los viajes y el modelo de bicicleta (FR-11).
-- La velocidad usa la distancia en línea recta entre estaciones, así que es una cota inferior
-- de la real; sirve para comparar modelos, no como velocidad absoluta. Excluye ida y vuelta
-- (distancia 0).

select
    bike_model.bike_model,
    count(*) as trips,
    round(100.0 * count(*) / sum(count(*)) over (), 2) as pct_trips,
    round(avg(trip.duration_minutes), 2) as avg_duration_minutes,
    round((percentile_cont(0.25) within group (order by trip.duration_minutes))::numeric, 2)
        as p25_duration_minutes,
    round((percentile_cont(0.5) within group (order by trip.duration_minutes))::numeric, 2)
        as median_duration_minutes,
    round((percentile_cont(0.75) within group (order by trip.duration_minutes))::numeric, 2)
        as p75_duration_minutes,
    round((percentile_cont(0.9) within group (order by trip.duration_minutes))::numeric, 2)
        as p90_duration_minutes,
    round(100.0 * count(*) filter (where trip.is_round_trip) / count(*), 2) as pct_round_trips,
    round(avg(trip.distance_m) filter (where not trip.is_round_trip), 0) as avg_distance_m,
    round(
        3.6 * sum(trip.distance_m) filter (where not trip.is_round_trip)
        / sum(trip.duration_seconds) filter (
            where not trip.is_round_trip and trip.distance_m is not null
        ),
        2
    ) as avg_speed_kmh
from {{ ref('fct_trips') }} as trip
inner join {{ ref('dim_bike_model') }} as bike_model
    on trip.bike_model_id = bike_model.bike_model_id
group by bike_model.bike_model
