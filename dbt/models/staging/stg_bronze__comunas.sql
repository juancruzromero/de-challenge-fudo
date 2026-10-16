-- Comunas tipadas: la geometría GeoJSON pasa a MultiPolygon PostGIS en WGS84.
-- El GeoJSON viene en CRS84 (lon/lat), que equivale a SRID 4326.
select
    {{ clean_number('comuna', 'smallint') }} as comuna,
    {{ clean_text('barrios') }} as barrios,
    {{ clean_number('perimetro') }} as perimeter_m,
    {{ clean_number('area') }} as area_m2,
    -- sqlfluff no reconoce el tipo con modificadores geometry(...): se ignora LT01 ahí.
    st_multi(
        st_setsrid(st_geomfromgeojson(geometry), 4326)
    )::geometry(multipolygon, 4326) as geom -- noqa: LT01
from {{ source('bronze', 'comunas') }}
