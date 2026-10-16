-- Consultas representativas del dashboard de Metabase (T7.2), para medir con make bench.
-- Cada sentencia lleva su nombre en un comentario `-- name:`. Leen gold como bi_reader.

-- name: d1_top_od_month
-- Top 20 recorridos origen-destino de un mes (filtro de mes del dashboard).
select
    origin_station_name,
    destination_station_name,
    trips,
    median_duration_minutes
from gold.agg_station_od_monthly
where month_start = date '2025-03-01'
order by trips desc
limit 20;

-- name: d1_top_od_month_from_fct
-- La misma consulta sin el agregado, directo sobre fct_trips: lo que costaría sin
-- agg_station_od_monthly.
select
    origin.station_name as origin_station_name,
    destination.station_name as destination_station_name,
    count(*) as trips,
    percentile_cont(0.5) within group (order by trip.duration_minutes) as median_duration_minutes
from gold.fct_trips as trip
inner join gold.dim_station as origin
    on trip.origin_station_id = origin.station_id
inner join gold.dim_station as destination
    on trip.destination_station_id = destination.station_id
where trip.start_date >= date '2025-03-01' and trip.start_date < date '2025-04-01'
group by origin.station_name, destination.station_name
order by trips desc
limit 20;

-- name: d2_top_od_by_comuna
-- Top 20 recorridos del año que salen de una comuna (filtro de comuna del dashboard).
select
    origin_station_name,
    destination_station_name,
    destination_comuna_label,
    sum(trips) as trips
from gold.agg_station_od_monthly
where origin_comuna_label = 'Comuna 1'
group by origin_station_name, destination_station_name, destination_comuna_label
order by trips desc
limit 20;

-- name: d3_monthly_trend
-- Evolución mensual de viajes (serie de tiempo del dashboard).
select
    month_start,
    sum(trips) as trips
from gold.agg_station_od_monthly
group by month_start
order by month_start;

-- name: d4_station_map
-- Viajes que salen de cada estación en el año, con coordenadas (mapa de estaciones).
select
    origin_station_id,
    origin_station_name,
    origin_latitude,
    origin_longitude,
    sum(trips) as trips
from gold.agg_station_od_monthly
where origin_latitude is not null
group by origin_station_id, origin_station_name, origin_latitude, origin_longitude;

-- name: d5_comuna_matrix
-- Matriz comuna de origen × comuna de destino en el año.
select
    origin_comuna_label,
    destination_comuna_label,
    sum(trips) as trips
from gold.agg_station_od_monthly
group by origin_comuna_label, destination_comuna_label;

-- name: d6_station_drilldown
-- Destinos de una estación, mes a mes (detalle de una estación).
select
    month_start,
    destination_station_name,
    trips
from gold.agg_station_od_monthly
where origin_station_id = 14
order by month_start asc, trips desc;
