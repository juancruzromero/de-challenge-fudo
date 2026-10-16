-- Atributos de estación tal como aparecen en cada viaje, apilando origen y destino.
-- Se usan solo para completar las estaciones que no están en el catálogo (FR-05).
with trip_ends as (
    select
        id_estacion_origen as station_id,
        nombre_estacion_origen as station_name,
        direccion_estacion_origen as address,
        lat_estacion_origen as latitude,
        long_estacion_origen as longitude
    from {{ source('bronze', 'trips') }}

    union all

    select
        id_estacion_destino as station_id,
        nombre_estacion_destino as station_name,
        direccion_estacion_destino as address,
        lat_estacion_destino as latitude,
        long_estacion_destino as longitude
    from {{ source('bronze', 'trips') }}
)

select
    {{ clean_id('station_id') }} as station_id,
    {{ clean_text('station_name') }} as station_name,
    {{ clean_text('address') }} as address,
    {{ clean_latitude('latitude') }} as latitude,
    {{ clean_longitude('longitude') }} as longitude
from trip_ends
