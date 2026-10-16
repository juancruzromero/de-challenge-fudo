{{
    config(
        indexes=[
            {'columns': ['station_id'], 'unique': true},
            {'columns': ['geom'], 'type': 'gist'},
        ]
    )
}}

-- Estaciones (ADR 001 y ADR 002):
-- 1. El catálogo actual es la fuente.
-- 2. Las estaciones de los viajes que no están en el catálogo se completan con los atributos
--    más frecuentes en los viajes (source = 'trips').
-- 3. La comuna se asigna por punto en polígono; si no cae en ninguno, la más cercana.
-- 4. Una estación sin coordenadas válidas se conserva con comuna NULL y
--    comuna_assignment = 'unknown': hoy es solo la 510 "[Valet] Galpón", que en los 176 viajes
--    donde aparece trae lat/long en 0. Así ningún viaje pierde su estación.

with catalog as (
    select
        station_id,
        station_number,
        station_name,
        address,
        latitude,
        longitude,
        'catalog' as source
    from {{ ref('stg_bronze__stations') }}
),

missing_from_catalog as (
    select
        trip_station.station_id,
        trip_station.station_name,
        trip_station.address,
        trip_station.latitude,
        trip_station.longitude,
        sum(trip_station.trip_ends) as trip_ends
    from {{ ref('stg_bronze__trip_stations') }} as trip_station
    where
        trip_station.station_id is not null
        and not exists (
            select 1
            from catalog
            where catalog.station_id = trip_station.station_id
        )
    group by
        trip_station.station_id,
        trip_station.station_name,
        trip_station.address,
        trip_station.latitude,
        trip_station.longitude
),

from_trips as (
    select distinct on (station_id)
        station_id,
        null::integer as station_number,
        station_name,
        address,
        latitude,
        longitude,
        'trips' as source
    from missing_from_catalog
    -- Primero las variantes con coordenadas válidas; entre ellas, la más frecuente.
    order by
        station_id asc,
        (latitude is not null and longitude is not null) desc,
        trip_ends desc,
        station_name asc
),

all_stations as (
    select
        station_id,
        station_number,
        station_name,
        address,
        latitude,
        longitude,
        {{ make_point('longitude', 'latitude') }} as geom,
        source
    from catalog

    union all

    select
        station_id,
        station_number,
        station_name,
        address,
        latitude,
        longitude,
        {{ make_point('longitude', 'latitude') }} as geom,
        source
    from from_trips
)

select
    station.station_id,
    station.station_number,
    station.station_name,
    station.address,
    station.latitude,
    station.longitude,
    station.geom,
    coalesce(containing.comuna, nearest.comuna) as comuna,
    case
        when containing.comuna is not null then 'contains'
        when nearest.comuna is not null then 'nearest'
        else 'unknown'
    end as comuna_assignment,
    station.source
from all_stations as station
left join lateral (
    select comuna.comuna
    from {{ ref('comunas') }} as comuna
    where st_contains(comuna.geom, station.geom)
    -- Un punto justo en el límite entre dos comunas: gana la de menor número.
    order by comuna.comuna
    limit 1
) as containing on true
left join lateral (
    select comuna.comuna
    from {{ ref('comunas') }} as comuna
    where containing.comuna is null and station.geom is not null
    order by comuna.geom <-> station.geom
    limit 1
) as nearest on true
