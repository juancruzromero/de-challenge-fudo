{{
    config(
        indexes=[
            {'columns': ['bike_model_id'], 'unique': true},
            {'columns': ['bike_model'], 'unique': true},
        ]
    )
}}

-- Modelos de bicicleta presentes en los viajes, con una clave numérica estable (orden alfabético).
select
    dense_rank() over (order by bike_model)::smallint as bike_model_id,
    bike_model
from (select distinct bike_model from {{ ref('trips') }}) as models
