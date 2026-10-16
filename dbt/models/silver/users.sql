{{
    config(
        indexes=[
            {'columns': ['user_id'], 'unique': true},
        ]
    )
}}

-- Usuarios con alta en 2024 y 2025, unificados (ADR 003). Los inválidos van a users_rejected.
select
    user_id,
    gender,
    age,
    signed_up_at,
    signed_up_at::date as signup_date,
    signup_year,
    has_dni,
    source_file
from {{ ref('users_validated') }}
where reject_reason is null
