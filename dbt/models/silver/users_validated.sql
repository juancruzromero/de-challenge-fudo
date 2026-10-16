{{ config(materialized='ephemeral') }}

-- Usuarios de los dos archivos con un reject_reason por fila (FR-07, FR-08).
-- No se materializa: lo leen users (válidos) y users_rejected (el resto).

with all_users as (
    select * from {{ ref('stg_bronze__users_2024') }}
    union all
    select * from {{ ref('stg_bronze__users_2025') }}
),

ranked as (
    select
        *,
        -- Mismo ID en los dos archivos: gana el alta más antigua (FR-07).
        row_number() over (
            partition by user_id
            order by signed_up_at asc nulls last, signup_year asc, source_row_number asc
        ) as user_id_rank
    from all_users
)

select
    user_id,
    gender,
    reported_age,
    -- Edad fuera de [15, 100] (incluye años como "2,024"): NULL, el usuario se conserva.
    case
        when reported_age between 15 and 100 and reported_age = trunc(reported_age)
            then reported_age::smallint
    end as age,
    signed_up_at,
    has_dni,
    signup_year,
    source_file,
    source_row_number,
    case
        when user_id is null then 'invalid_user_id'
        when signed_up_at is null then 'invalid_signup_date'
        when user_id_rank > 1 then 'duplicate_user_id'
    end as reject_reason
from ranked
