{#-
    Ranking de comunas por viajes, según la estación de origen (Q1) o de destino (Q2).
    trips_per_station normaliza por la cantidad de estaciones: la comuna con más viajes suele
    ser la que tiene más estaciones, no necesariamente la de mayor uso por estación.
-#}
{% macro comuna_trip_ranking(station_column) -%}
with trips_by_comuna as (
    select
        station.comuna,
        station.comuna_label,
        count(*) as trips
    from {{ ref('fct_trips') }} as trip
    inner join {{ ref('dim_station') }} as station
        on trip.{{ station_column }} = station.station_id
    group by station.comuna, station.comuna_label
),

stations_by_comuna as (
    select
        comuna_label,
        count(*) as stations
    from {{ ref('dim_station') }}
    group by comuna_label
)

select
    rank() over (order by trips_by_comuna.trips desc)::smallint as ranking,
    trips_by_comuna.comuna,
    trips_by_comuna.comuna_label,
    trips_by_comuna.trips,
    round(100.0 * trips_by_comuna.trips / sum(trips_by_comuna.trips) over (), 2) as pct_trips,
    stations_by_comuna.stations,
    round(trips_by_comuna.trips::numeric / stations_by_comuna.stations, 0) as trips_per_station
from trips_by_comuna
inner join stations_by_comuna
    on trips_by_comuna.comuna_label = stations_by_comuna.comuna_label
{%- endmacro %}
