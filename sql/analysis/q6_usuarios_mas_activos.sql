-- Q6: ¿Quiénes fueron los usuarios más activos durante 2025?
--
-- Ranking por cantidad de viajes; desempata la duración total. Sin perfil = alta anterior a
-- 2024 (no está en los archivos de usuarios, ADR 003).
-- Versión materializada para el dashboard (top 100): gold.mart_q6_top_users.
--
-- Se agrega en pasos (usuario × día, usuario × estación) en lugar de count(distinct) y mode():
-- esos agregados piden la entrada ordenada por usuario y el planner terminaba leyendo
-- fct_trips por índice, con acceso aleatorio, tres veces. Así baja de ~11,5 s a ~2 s
-- (sql/optimization/README.md).

with viajes_por_usuario_y_dia as (
    select
        user_id,
        start_date,
        count(*) as viajes,
        sum(duration_seconds) as segundos
    from gold.fct_trips
    group by user_id, start_date
),

viajes_por_usuario as (
    select
        user_id,
        sum(viajes) as viajes,
        round(sum(segundos) / 3600.0, 1) as horas_totales,
        count(*) as dias_con_viajes
    from viajes_por_usuario_y_dia
    group by user_id
),

top_usuarios as (
    select
        *,
        row_number() over (order by viajes desc, horas_totales desc) as ranking
    from viajes_por_usuario
    order by ranking
    limit 20
),

viajes_por_estacion as (
    select
        viaje.user_id,
        viaje.origin_station_id,
        count(*) as viajes
    from gold.fct_trips as viaje
    inner join top_usuarios
        on viaje.user_id = top_usuarios.user_id
    group by viaje.user_id, viaje.origin_station_id
),

-- Estación de origen más usada por cada usuario del top; empate: el ID menor.
estacion_favorita as (
    select distinct on (user_id)
        user_id,
        origin_station_id
    from viajes_por_estacion
    order by user_id asc, viajes desc, origin_station_id asc
)

select
    top_usuarios.ranking,
    top_usuarios.user_id,
    top_usuarios.viajes,
    top_usuarios.horas_totales,
    top_usuarios.dias_con_viajes,
    round(top_usuarios.viajes / top_usuarios.dias_con_viajes, 1) as viajes_por_dia_con_viajes,
    estacion.station_name as estacion_favorita,
    case when usuario.has_profile then 'sí' else 'no' end as tiene_perfil,
    usuario.age_group as rango_etario
from top_usuarios
inner join estacion_favorita
    on top_usuarios.user_id = estacion_favorita.user_id
inner join gold.dim_user as usuario
    on top_usuarios.user_id = usuario.user_id
inner join gold.dim_station as estacion
    on estacion_favorita.origin_station_id = estacion.station_id
order by top_usuarios.ranking;
