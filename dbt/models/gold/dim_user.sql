{{
    config(
        indexes=[
            {'columns': ['user_id'], 'unique': true},
            {'columns': ['signup_month']},
        ]
    )
}}

-- Usuarios (ADR 003): todos los que viajaron en 2025 y todos los de los archivos de alta 2024 y
-- 2025, aunque no hayan viajado (Q4 necesita esos ceros por cohorte).
-- has_profile = true: está en users y tiene edad y fecha de alta.
-- has_profile = false: alta anterior a 2024; el género sale del más frecuente en sus viajes.

with trip_users as (
    select
        user_id,
        mode() within group (order by gender) as trips_gender
    from {{ ref('trips') }}
    group by user_id
),

profiles as (
    select * from {{ ref('users') }}
),

all_users as (
    select
        coalesce(profiles.user_id, trip_users.user_id) as user_id,
        profiles.user_id is not null as has_profile,
        profiles.gender as profile_gender,
        trip_users.trips_gender,
        profiles.age,
        profiles.signed_up_at,
        profiles.signup_date,
        profiles.signup_year,
        profiles.has_dni
    from profiles
    full outer join trip_users
        on profiles.user_id = trip_users.user_id
)

select
    user_id,
    has_profile,
    coalesce(profile_gender, trips_gender) as gender,
    case
        when profile_gender is not null then 'profile'
        when trips_gender is not null then 'trips'
    end as gender_source,
    age,
    case
        when age is null then 'Sin dato'
        when age < 25 then '15-24'
        when age < 35 then '25-34'
        when age < 45 then '35-44'
        when age < 55 then '45-54'
        when age < 65 then '55-64'
        else '65+'
    end as age_group,
    signed_up_at,
    signup_date,
    signup_year,
    date_trunc('month', signup_date)::date as signup_month,
    has_dni
from all_users
