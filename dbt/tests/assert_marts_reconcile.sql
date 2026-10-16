-- Los marts cuadran entre sí y con el modelo estrella (FR-11).
-- El test falla si devuelve filas: cada fila es un control que no da lo esperado.
with checks as (
    select
        'q1 suma los viajes de fct_trips' as check_name,
        (select sum(trips) from {{ ref('mart_q1_comunas_origin') }}) as actual,
        (select count(*) from {{ ref('fct_trips') }}) as expected

    union all

    select
        'q2 suma los viajes de fct_trips' as check_name,
        (select sum(trips) from {{ ref('mart_q2_comunas_destination') }}) as actual,
        (select count(*) from {{ ref('fct_trips') }}) as expected

    union all

    select
        'q3 suma los usuarios con perfil' as check_name,
        (select sum(users) from {{ ref('mart_q3_trips_by_age_group') }}) as actual,
        (
            select count(*)
            from {{ ref('dim_user') }}
            where has_profile
        ) as expected

    union all

    select
        'q4 suma los usuarios con perfil' as check_name,
        (select sum(users) from {{ ref('mart_q4_trips_by_signup_month') }}) as actual,
        (
            select count(*)
            from {{ ref('dim_user') }}
            where has_profile
        ) as expected

    union all

    select
        'q3 y q4 suman los mismos viajes' as check_name,
        (select sum(trips) from {{ ref('mart_q3_trips_by_age_group') }}) as actual,
        (select sum(trips) from {{ ref('mart_q4_trips_by_signup_month') }}) as expected

    union all

    select
        'q5 suma los viajes de fct_trips' as check_name,
        (select sum(trips) from {{ ref('mart_q5_duration_by_bike_model') }}) as actual,
        (select count(*) from {{ ref('fct_trips') }}) as expected

    union all

    select
        'q5 por distancia suma los viajes de fct_trips' as check_name,
        (select sum(trips) from {{ ref('mart_q5_duration_by_model_and_distance') }}) as actual,
        (select count(*) from {{ ref('fct_trips') }}) as expected
)

select
    check_name,
    actual,
    expected
from checks
where actual is distinct from expected
