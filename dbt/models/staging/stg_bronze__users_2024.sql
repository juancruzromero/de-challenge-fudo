-- Usuarios con alta en 2024, tipados al esquema común de usuarios (FR-01c).
-- Este archivo no trae la columna de DNI.
select
    {{ clean_id('id_usuario') }} as user_id,
    {{ clean_gender('genero_usuario') }} as gender,
    {{ clean_number('edad_usuario') }} as reported_age,
    {{ clean_timestamp('fecha_alta', 'hora_alta') }} as signed_up_at,
    null::boolean as has_dni,
    2024 as signup_year,
    _source_file as source_file,
    _row_number as source_row_number
from {{ source('bronze', 'users_2024') }}
