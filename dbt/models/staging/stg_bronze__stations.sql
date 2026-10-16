-- Catálogo de estaciones del sistema actual, tipado. barrio, comuna y emplazamiento se
-- descartan: vienen vacíos en todas las filas (spec.md §2).
select
    {{ clean_id('id') }} as station_id,
    {{ clean_number('numero_de_estacion', 'integer') }} as station_number,
    {{ clean_text('nombre') }} as station_name,
    {{ clean_text('direccion') }} as address,
    {{ clean_latitude('latitud') }} as latitude,
    {{ clean_longitude('longitud') }} as longitude
from {{ source('bronze', 'stations') }}
