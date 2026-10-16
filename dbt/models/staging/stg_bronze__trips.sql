-- Viajes tipados. Los nombres, direcciones y coordenadas de estación del archivo no pasan:
-- los atributos de la estación salen de silver.stations (ver stg_bronze__trip_stations).
select
    {{ clean_id('id_recorrido') }} as trip_id,
    {{ clean_number('duracion_recorrido') }} as duration_seconds,
    {{ clean_timestamp('fecha_origen_recorrido') }} as started_at,
    {{ clean_timestamp('fecha_destino_recorrido') }} as ended_at,
    {{ clean_id('id_estacion_origen') }} as origin_station_id,
    {{ clean_id('id_estacion_destino') }} as destination_station_id,
    {{ clean_id('id_usuario') }} as user_id,
    case
        when upper(trim(modelo_bicicleta)) in ('FIT', 'ICONIC') then upper(trim(modelo_bicicleta))
    end as bike_model,
    {{ clean_gender('genero') }} as gender,
    _source_file as source_file,
    _row_number as source_row_number
from {{ source('bronze', 'trips') }}
