-- Q4: relación entre la cantidad de viajes y la fecha de alta (FR-11). Grano: mes de alta.
-- Universo: usuarios con perfil (altas 2024-2025, ADR 003), incluidos los que no viajaron.
--
-- trips_per_user favorece a las altas viejas: un alta de enero de 2024 pudo viajar todo 2025 y
-- una de diciembre de 2025, unos pocos días. trips_per_30_days normaliza por exposición:
-- viajes cada 30 días en los que el usuario ya estaba dado de alta durante 2025.

select
    signup_month,
    to_char(signup_month, 'YYYY-MM') as signup_year_month,
    signup_year,
    count(*) as users,
    count(*) filter (where trips > 0) as active_users,
    round(100.0 * count(*) filter (where trips > 0) / count(*), 1) as pct_active_users,
    sum(trips) as trips,
    round(sum(trips)::numeric / count(*), 2) as trips_per_user,
    round(sum(trips)::numeric / nullif(count(*) filter (where trips > 0), 0), 2)
        as trips_per_active_user,
    round(avg(exposure_days), 0) as avg_exposure_days,
    round(30.0 * sum(trips) / sum(exposure_days), 2) as trips_per_30_days
from {{ ref('int_user_trips') }}
where has_profile
group by signup_month, signup_year
