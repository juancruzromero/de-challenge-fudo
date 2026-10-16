-- Una estación sin ubicación (comuna_assignment = 'unknown') solo puede venir de los viajes:
-- las del catálogo tienen coordenadas válidas en todas las filas (spec.md §2).
-- El test falla si devuelve filas.
select
    station_id,
    station_name,
    source,
    comuna_assignment
from {{ ref('stations') }}
where
    comuna_assignment = 'unknown'
    and (source <> 'trips' or geom is not null or comuna is not null)
