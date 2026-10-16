{{
    config(
        indexes=[
            {'columns': ['station_id'], 'unique': true},
            {'columns': ['comuna']},
            {'columns': ['geom'], 'type': 'gist'},
        ]
    )
}}

-- Estaciones con su comuna (ADR 001, ADR 002). comuna_label agrupa en "Sin ubicación" a la
-- estación 510, que no tiene coordenadas válidas.
select
    station_id,
    station_number,
    station_name,
    address,
    latitude,
    longitude,
    geom,
    comuna,
    coalesce('Comuna ' || comuna, 'Sin ubicación') as comuna_label,
    comuna_assignment,
    source
from {{ ref('stations') }}
