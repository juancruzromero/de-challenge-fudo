-- Q2: ¿Qué comunas reciben más viajes?
--
-- Igual que Q1, por la comuna de la estación de destino. balance = llegadas - salidas: positivo
-- si la comuna recibe más viajes de los que genera (atrae), negativo si genera más (expulsa).
-- "Sin ubicación" es la estación 510 "[Valet] Galpón", que no tiene coordenadas.
-- Versión materializada para el dashboard: gold.mart_q2_comunas_destination.

with llegadas as (
    select
        estacion.comuna_label as comuna,
        count(*) as viajes
    from gold.fct_trips as viaje
    inner join gold.dim_station as estacion
        on viaje.destination_station_id = estacion.station_id
    group by estacion.comuna_label
),

salidas as (
    select
        estacion.comuna_label as comuna,
        count(*) as viajes
    from gold.fct_trips as viaje
    inner join gold.dim_station as estacion
        on viaje.origin_station_id = estacion.station_id
    group by estacion.comuna_label
)

select
    rank() over (order by llegadas.viajes desc) as ranking,
    llegadas.comuna,
    llegadas.viajes as viajes_recibidos,
    round(100.0 * llegadas.viajes / sum(llegadas.viajes) over (), 2) as pct_viajes,
    coalesce(salidas.viajes, 0) as viajes_que_salen,
    llegadas.viajes - coalesce(salidas.viajes, 0) as balance
from llegadas
left join salidas
    on llegadas.comuna = salidas.comuna
order by ranking;
