{{
    config(
        indexes=[
            {'columns': ['comuna'], 'unique': true},
            {'columns': ['geom'], 'type': 'gist'},
        ]
    )
}}

-- Comunas de la Ciudad (ADR 001).
select
    comuna,
    'Comuna ' || comuna as comuna_label,
    barrios,
    round(area_m2 / 1000000, 2) as area_km2,
    perimeter_m,
    geom
from {{ ref('comunas') }}
