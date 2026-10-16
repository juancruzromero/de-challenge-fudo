-- Q3: correlación y regresión lineal simple entre edad y viajes, a nivel usuario (FR-11).
-- Una fila por universo: todos los usuarios con perfil y edad válida, o solo los activos
-- (al menos un viaje). Es una correlación, no una relación causal.

with users_with_age as (
    select
        age,
        trips
    from {{ ref('int_user_trips') }}
    where has_profile and age is not null
),

universes as (
    select
        'Usuarios con perfil y edad' as universe,
        age,
        trips
    from users_with_age

    union all

    select
        'Usuarios activos (al menos 1 viaje)' as universe,
        age,
        trips
    from users_with_age
    where trips > 0
)

select
    universe,
    count(*) as users,
    sum(trips) as trips,
    round(100.0 * sum(trips) / (select count(*) from {{ ref('fct_trips') }}), 2)
        as pct_of_all_trips,
    round(corr(trips, age)::numeric, 4) as pearson_r,
    round(regr_slope(trips, age)::numeric, 4) as slope_trips_per_year_of_age,
    round(regr_intercept(trips, age)::numeric, 2) as intercept,
    round(regr_r2(trips, age)::numeric, 4) as r_squared
from universes
group by universe
