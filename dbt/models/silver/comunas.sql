{{
    config(
        indexes=[
            {'columns': ['comuna'], 'unique': true},
            {'columns': ['geom'], 'type': 'gist'},
        ]
    )
}}

-- Polígonos de las 15 comunas (ADR 001).
select
    comuna,
    barrios,
    perimeter_m,
    area_m2,
    geom
from {{ ref('stg_bronze__comunas') }}
