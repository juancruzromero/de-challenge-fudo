-- Q5: ¿Qué relación hay entre la duración de los viajes y el modelo de bicicleta?
--
-- La mediana y los percentiles son más representativos que la media: hay viajes de hasta 24 h
-- que la tiran para arriba.
-- Versiones materializadas: gold.mart_q5_duration_by_bike_model y
-- gold.mart_q5_duration_by_model_and_distance.

-- 1. Duración por modelo.
select
    modelo.bike_model as modelo,
    count(*) as viajes,
    round(avg(viaje.duration_minutes), 2) as duracion_media_min,
    round((percentile_cont(0.25) within group (order by viaje.duration_minutes))::numeric, 2)
        as p25_min,
    round((percentile_cont(0.5) within group (order by viaje.duration_minutes))::numeric, 2)
        as mediana_min,
    round((percentile_cont(0.75) within group (order by viaje.duration_minutes))::numeric, 2)
        as p75_min,
    round((percentile_cont(0.9) within group (order by viaje.duration_minutes))::numeric, 2)
        as p90_min
from gold.fct_trips as viaje
inner join gold.dim_bike_model as modelo
    on viaje.bike_model_id = modelo.bike_model_id
group by modelo.bike_model
order by modelo.bike_model;

-- 2. Control por distancia: la misma comparación dentro de cada tramo de distancia en línea
-- recta entre estaciones. Si las duraciones coinciden tramo a tramo, el modelo no influye: las
-- diferencias globales vendrían de para qué recorridos se usa cada uno.
select
    case
        when viaje.is_round_trip then '0. Ida y vuelta'
        when viaje.distance_m < 1000 then '1. Menos de 1 km'
        when viaje.distance_m < 2000 then '2. 1 a 2 km'
        when viaje.distance_m < 3000 then '3. 2 a 3 km'
        when viaje.distance_m < 5000 then '4. 3 a 5 km'
        else '5. 5 km o más'
    end as tramo_de_distancia,
    round(
        (
            percentile_cont(0.5) within group (order by viaje.duration_minutes)
            filter (where modelo.bike_model = 'FIT')
        )::numeric,
        2
    ) as mediana_fit_min,
    round(
        (
            percentile_cont(0.5) within group (order by viaje.duration_minutes)
            filter (where modelo.bike_model = 'ICONIC')
        )::numeric,
        2
    ) as mediana_iconic_min,
    count(*) as viajes
from gold.fct_trips as viaje
inner join gold.dim_bike_model as modelo
    on viaje.bike_model_id = modelo.bike_model_id
where viaje.distance_m is not null
group by tramo_de_distancia
order by tramo_de_distancia;
