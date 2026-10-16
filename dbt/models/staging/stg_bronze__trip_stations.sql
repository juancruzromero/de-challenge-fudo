-- Atributos de estación tal como aparecen en los viajes, apilando origen y destino, con la
-- cantidad de extremos de viaje de cada variante. Se usan solo para completar las estaciones
-- que no están en el catálogo (FR-05).
-- Los 6,3 M extremos de viaje son ~440 variantes distintas: se agrupan los valores crudos en un
-- solo escaneo de bronze.trips y la limpieza corre sobre esas pocas filas (T6.2).
with trip_ends as (
    select
        trip_end.station_id,
        trip_end.station_name,
        trip_end.address,
        trip_end.latitude,
        trip_end.longitude,
        count(*) as trip_ends
    from {{ source('bronze', 'trips') }} as trip
    cross join
        lateral (
            values
            (
                trip.id_estacion_origen,
                trip.nombre_estacion_origen,
                trip.direccion_estacion_origen,
                trip.lat_estacion_origen,
                trip.long_estacion_origen
            ),
            (
                trip.id_estacion_destino,
                trip.nombre_estacion_destino,
                trip.direccion_estacion_destino,
                trip.lat_estacion_destino,
                trip.long_estacion_destino
            )
        ) as trip_end (station_id, station_name, address, latitude, longitude)
    group by
        trip_end.station_id,
        trip_end.station_name,
        trip_end.address,
        trip_end.latitude,
        trip_end.longitude
)

select
    {{ clean_id('station_id') }} as station_id,
    {{ clean_text('station_name') }} as station_name,
    {{ clean_text('address') }} as address,
    {{ clean_latitude('latitude') }} as latitude,
    {{ clean_longitude('longitude') }} as longitude,
    trip_ends
from trip_ends
