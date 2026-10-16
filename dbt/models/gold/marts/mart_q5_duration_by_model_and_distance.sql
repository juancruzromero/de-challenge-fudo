-- Q5 (control): duración por modelo dentro de cada tramo de distancia. Si un modelo se usa más
-- para viajes largos, su duración media sube sin que la bici sea más lenta: comparar dentro del
-- mismo tramo separa el efecto del modelo del efecto del recorrido.

with banded as (
    select
        trip.bike_model_id,
        trip.duration_minutes,
        case
            when trip.is_round_trip then 0
            when trip.distance_m is null then 99
            when trip.distance_m < 1000 then 1
            when trip.distance_m < 2000 then 2
            when trip.distance_m < 3000 then 3
            when trip.distance_m < 5000 then 4
            else 5
        end as distance_band_order
    from {{ ref('fct_trips') }} as trip
)

select
    banded.distance_band_order::smallint as distance_band_order,
    case banded.distance_band_order
        when 0 then 'Ida y vuelta'
        when 1 then 'Menos de 1 km'
        when 2 then '1 a 2 km'
        when 3 then '2 a 3 km'
        when 4 then '3 a 5 km'
        when 5 then '5 km o más'
        else 'Sin distancia'
    end as distance_band,
    bike_model.bike_model,
    count(*) as trips,
    round(avg(banded.duration_minutes), 2) as avg_duration_minutes,
    round((percentile_cont(0.5) within group (order by banded.duration_minutes))::numeric, 2)
        as median_duration_minutes
from banded
inner join {{ ref('dim_bike_model') }} as bike_model
    on banded.bike_model_id = bike_model.bike_model_id
group by banded.distance_band_order, bike_model.bike_model
