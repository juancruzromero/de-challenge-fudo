-- Q6: usuarios más activos de 2025 (FR-11). Top N por cantidad de viajes (var top_users);
-- desempata la duración total y después el ID, para que el ranking sea estable.

with ranked as (
    select
        user_id,
        has_profile,
        gender,
        age_group,
        signup_year,
        trips,
        duration_seconds,
        active_days,
        row_number() over (order by trips desc, duration_seconds desc, user_id asc) as ranking
    from {{ ref('int_user_trips') }}
    where trips > 0
),

top_users as (
    select * from ranked
    where ranking <= {{ var('top_users') }}
),

trips_by_origin as (
    select
        trip.user_id,
        trip.origin_station_id,
        count(*) as trips_from_station
    from {{ ref('fct_trips') }} as trip
    inner join top_users
        on trip.user_id = top_users.user_id
    group by trip.user_id, trip.origin_station_id
),

favorite_station as (
    select distinct on (user_id)
        user_id,
        origin_station_id,
        trips_from_station
    from trips_by_origin
    order by user_id asc, trips_from_station desc, origin_station_id asc
)

select
    top_users.ranking::smallint as ranking,
    top_users.user_id,
    top_users.trips,
    round(top_users.duration_seconds / 3600.0, 1) as total_hours,
    round(top_users.duration_seconds / 60.0 / top_users.trips, 1) as avg_duration_minutes,
    top_users.active_days,
    round(top_users.trips::numeric / top_users.active_days, 1) as trips_per_active_day,
    station.station_name as favorite_origin_station,
    favorite_station.trips_from_station as trips_from_favorite_station,
    top_users.has_profile,
    top_users.gender,
    top_users.age_group,
    top_users.signup_year
from top_users
inner join favorite_station
    on top_users.user_id = favorite_station.user_id
inner join {{ ref('dim_station') }} as station
    on favorite_station.origin_station_id = station.station_id
