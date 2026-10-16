-- Q4: ¿Qué relación hay entre la cantidad de viajes y la fecha de alta de los usuarios?
--
-- Universo: usuarios con perfil (altas 2024 y 2025, ADR 003), incluidos los que no viajaron.
-- Agrupado por mes de alta (cohorte).
--
-- Cuidado con "viajes por usuario": un alta de enero de 2024 pudo viajar los 365 días de 2025 y
-- una de diciembre de 2025, unos pocos. viajes_cada_30_dias normaliza por exposición: viajes
-- cada 30 días en los que el usuario ya estaba dado de alta durante 2025.
-- Versión materializada para el dashboard: gold.mart_q4_trips_by_signup_month.

with usuarios as (
    select
        usuario.user_id,
        usuario.signup_month,
        usuario.signup_year,
        count(viaje.trip_id) as viajes,
        date '2025-12-31' - greatest(usuario.signup_date, date '2025-01-01') + 1
            as dias_de_exposicion
    from gold.dim_user as usuario
    left join gold.fct_trips as viaje
        on usuario.user_id = viaje.user_id
    where usuario.has_profile
    group by usuario.user_id, usuario.signup_month, usuario.signup_year, usuario.signup_date
)

select
    to_char(signup_month, 'YYYY-MM') as mes_de_alta,
    count(*) as usuarios,
    round(100.0 * count(*) filter (where viajes > 0) / count(*), 1) as pct_usuarios_activos,
    sum(viajes) as viajes,
    round(sum(viajes)::numeric / count(*), 2) as viajes_por_usuario,
    round(avg(dias_de_exposicion), 0) as dias_de_exposicion_promedio,
    round(30.0 * sum(viajes) / sum(dias_de_exposicion), 2) as viajes_cada_30_dias
from usuarios
group by signup_month
order by signup_month;

-- Resumen por año de alta: las altas 2025 siguen activas mucho más que las de 2024.
with usuarios as (
    select
        usuario.user_id,
        usuario.signup_year,
        count(viaje.trip_id) as viajes,
        date '2025-12-31' - greatest(usuario.signup_date, date '2025-01-01') + 1
            as dias_de_exposicion
    from gold.dim_user as usuario
    left join gold.fct_trips as viaje
        on usuario.user_id = viaje.user_id
    where usuario.has_profile
    group by usuario.user_id, usuario.signup_year, usuario.signup_date
)

select
    signup_year as anio_de_alta,
    count(*) as usuarios,
    round(100.0 * count(*) filter (where viajes > 0) / count(*), 1) as pct_usuarios_activos,
    round(sum(viajes)::numeric / count(*), 2) as viajes_por_usuario,
    round(30.0 * sum(viajes) / sum(dias_de_exposicion), 2) as viajes_cada_30_dias
from usuarios
group by signup_year
order by signup_year;
