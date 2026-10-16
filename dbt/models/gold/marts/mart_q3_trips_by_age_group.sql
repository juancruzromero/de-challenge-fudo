-- Q3: relación entre la edad de los usuarios y la cantidad de viajes (FR-11).
-- Universo: usuarios con perfil (altas 2024-2025, ADR 003), incluidos los que no viajaron.
-- pct_of_all_trips muestra qué parte del total de viajes explica cada grupo.

select
    case age_group
        when '15-24' then 1
        when '25-34' then 2
        when '35-44' then 3
        when '45-54' then 4
        when '55-64' then 5
        when '65+' then 6
        else 7
    end::smallint as sort_order,
    age_group,
    count(*) as users,
    count(*) filter (where trips > 0) as active_users,
    round(100.0 * count(*) filter (where trips > 0) / count(*), 1) as pct_active_users,
    sum(trips) as trips,
    round(sum(trips)::numeric / count(*), 2) as trips_per_user,
    round(sum(trips)::numeric / nullif(count(*) filter (where trips > 0), 0), 2)
        as trips_per_active_user,
    round(100.0 * sum(trips) / (select count(*) from {{ ref('fct_trips') }}), 2)
        as pct_of_all_trips
from {{ ref('int_user_trips') }}
where has_profile
group by age_group
