-- FR-05: toda estación que aparece en un viaje tiene que estar en silver.stations.
-- El test falla si devuelve filas (IDs de viajes sin estación).
select distinct trip_station.station_id
from {{ ref('stg_bronze__trip_stations') }} as trip_station
left join {{ ref('stations') }} as station
    on trip_station.station_id = station.station_id
where
    trip_station.station_id is not null
    and station.station_id is null
