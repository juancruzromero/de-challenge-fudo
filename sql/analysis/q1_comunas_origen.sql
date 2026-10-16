-- Q1: ¿De qué comunas parten más viajes?
--
-- Se cuentan los viajes 2025 según la comuna de la estación de origen. Además del total,
-- viajes por estación: la comuna con más viajes suele ser la que tiene más estaciones, así que
-- trips_per_station muestra mejor la intensidad de uso.
-- Versión materializada para el dashboard: gold.mart_q1_comunas_origin.

with viajes_por_comuna as (
    select
        estacion.comuna_label as comuna,
        count(*) as viajes
    from gold.fct_trips as viaje
    inner join gold.dim_station as estacion
        on viaje.origin_station_id = estacion.station_id
    group by estacion.comuna_label
),

estaciones_por_comuna as (
    select
        comuna_label as comuna,
        count(*) as estaciones
    from gold.dim_station
    group by comuna_label
)

select
    rank() over (order by viajes_por_comuna.viajes desc) as ranking,
    viajes_por_comuna.comuna,
    viajes_por_comuna.viajes,
    round(100.0 * viajes_por_comuna.viajes / sum(viajes_por_comuna.viajes) over (), 2)
        as pct_viajes,
    estaciones_por_comuna.estaciones,
    round(viajes_por_comuna.viajes::numeric / estaciones_por_comuna.estaciones, 0)
        as viajes_por_estacion
from viajes_por_comuna
inner join estaciones_por_comuna
    on viajes_por_comuna.comuna = estaciones_por_comuna.comuna
order by ranking;
