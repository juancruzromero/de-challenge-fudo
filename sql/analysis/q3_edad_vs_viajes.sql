-- Q3: ¿Qué relación hay entre la edad de los usuarios y la cantidad de viajes que hicieron?
--
-- Universo: usuarios con perfil (altas 2024 y 2025, ADR 003), que hacen el 49 % de los viajes.
-- Se incluyen los usuarios que no viajaron en 2025: sin ellos, "viajes por usuario" quedaría
-- inflado en los grupos con más abandono.
-- Versiones materializadas: gold.mart_q3_trips_by_age_group y gold.mart_q3_age_correlation.

-- 1. Por rango etario.
with viajes_por_usuario as (
    select
        usuario.user_id,
        usuario.age,
        usuario.age_group,
        count(viaje.trip_id) as viajes
    from gold.dim_user as usuario
    left join gold.fct_trips as viaje
        on usuario.user_id = viaje.user_id
    where usuario.has_profile
    group by usuario.user_id, usuario.age, usuario.age_group
)

select
    age_group as rango_etario,
    count(*) as usuarios,
    round(100.0 * count(*) filter (where viajes > 0) / count(*), 1) as pct_usuarios_activos,
    sum(viajes) as viajes,
    round(sum(viajes)::numeric / count(*), 2) as viajes_por_usuario,
    round(sum(viajes)::numeric / nullif(count(*) filter (where viajes > 0), 0), 2)
        as viajes_por_usuario_activo
from viajes_por_usuario
group by age_group
order by age_group = 'Sin dato', age_group;

-- 2. Correlación y regresión lineal simple viajes ~ edad, a nivel usuario.
-- pearson_r cerca de 0 y r_cuadrado cerca de 0: la edad casi no explica cuánto viaja alguien.
-- Es una correlación, no una relación causal.
with viajes_por_usuario as (
    select
        usuario.age,
        count(viaje.trip_id) as viajes
    from gold.dim_user as usuario
    left join gold.fct_trips as viaje
        on usuario.user_id = viaje.user_id
    where usuario.has_profile and usuario.age is not null
    group by usuario.user_id, usuario.age
)

select
    count(*) as usuarios,
    round(corr(viajes, age)::numeric, 4) as pearson_r,
    round(regr_slope(viajes, age)::numeric, 4) as viajes_por_anio_de_edad,
    round(regr_r2(viajes, age)::numeric, 4) as r_cuadrado
from viajes_por_usuario;
