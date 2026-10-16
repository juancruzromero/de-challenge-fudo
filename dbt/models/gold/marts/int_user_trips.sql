{{ config(materialized='ephemeral') }}

-- Viajes de 2025 por usuario, para todos los usuarios de dim_user (incluye los de 0 viajes).
-- exposure_days: días de 2025 en los que el usuario pudo viajar, desde su alta (o el 1 de
-- enero si se dio de alta antes) hasta el 31 de diciembre. NULL sin perfil (alta desconocida).
-- Lo usan Q3, Q4 y Q6; no se materializa.

with trips_by_user as (
    select
        user_id,
        count(*) as trips,
        sum(duration_seconds) as duration_seconds,
        count(distinct start_date) as active_days
    from {{ ref('fct_trips') }}
    group by user_id
)

select
    dim_user.user_id,
    dim_user.has_profile,
    dim_user.gender,
    dim_user.age,
    dim_user.age_group,
    dim_user.signup_date,
    dim_user.signup_month,
    dim_user.signup_year,
    coalesce(trips_by_user.trips, 0) as trips,
    coalesce(trips_by_user.duration_seconds, 0) as duration_seconds,
    coalesce(trips_by_user.active_days, 0) as active_days,
    make_date({{ var('analysis_year') }}, 12, 31)
    - greatest(dim_user.signup_date, make_date({{ var('analysis_year') }}, 1, 1))
    + 1 as exposure_days
from {{ ref('dim_user') }} as dim_user
left join trips_by_user
    on dim_user.user_id = trips_by_user.user_id
