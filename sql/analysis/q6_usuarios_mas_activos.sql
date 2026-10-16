-- Q6: ¿Quiénes fueron los usuarios más activos durante 2025?
--
-- Ranking por cantidad de viajes; desempata la duración total. Sin perfil = alta anterior a
-- 2024 (no está en los archivos de usuarios, ADR 003).
-- Versión materializada para el dashboard (top 100): gold.mart_q6_top_users.

with viajes_por_usuario as (
    select
        user_id,
        count(*) as viajes,
        round(sum(duration_seconds) / 3600.0, 1) as horas_totales,
        count(distinct start_date) as dias_con_viajes,
        mode() within group (order by origin_station_id) as estacion_favorita_id
    from gold.fct_trips
    group by user_id
)

select
    row_number() over (
        order by viajes_por_usuario.viajes desc, viajes_por_usuario.horas_totales desc
    ) as ranking,
    viajes_por_usuario.user_id,
    viajes_por_usuario.viajes,
    viajes_por_usuario.horas_totales,
    viajes_por_usuario.dias_con_viajes,
    round(viajes_por_usuario.viajes::numeric / viajes_por_usuario.dias_con_viajes, 1)
        as viajes_por_dia_con_viajes,
    estacion.station_name as estacion_favorita,
    case when usuario.has_profile then 'sí' else 'no' end as tiene_perfil,
    usuario.age_group as rango_etario
from viajes_por_usuario
inner join gold.dim_user as usuario
    on viajes_por_usuario.user_id = usuario.user_id
inner join gold.dim_station as estacion
    on viajes_por_usuario.estacion_favorita_id = estacion.station_id
order by ranking
limit 20;
