-- Viajes descartados por las reglas de calidad (FR-08), con el motivo y la fila de origen
-- para poder rastrearlos en bronze.
select
    reject_reason,
    source_file,
    source_row_number,
    trip_id,
    started_at,
    ended_at,
    duration_seconds,
    origin_station_id,
    destination_station_id,
    user_id,
    bike_model,
    gender
from {{ ref('trips_validated') }}
where reject_reason is not null
