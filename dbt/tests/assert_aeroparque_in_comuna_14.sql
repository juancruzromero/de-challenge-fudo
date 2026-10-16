-- ADR 001: AEROPARQUE (id 541) está sobre la costa, fuera de todos los polígonos.
-- Se le asigna la comuna más cercana, que tiene que ser la 14 (Palermo).
-- El test falla si devuelve filas.
select
    station_id,
    station_name,
    comuna,
    comuna_assignment
from {{ ref('stations') }}
where
    station_id = 541
    and (comuna is distinct from 14 or comuna_assignment is distinct from 'nearest')

union all

-- Y es la única estación asignada por cercanía.
select
    station_id,
    station_name,
    comuna,
    comuna_assignment
from {{ ref('stations') }}
where comuna_assignment = 'nearest' and station_id <> 541
