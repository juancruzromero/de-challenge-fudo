-- Usuarios con alta en 2025, tipados al esquema común de usuarios (FR-01c).
select
    {{ clean_id('id_cliente') }} as user_id,
    {{ clean_gender('genero_usuario') }} as gender,
    {{ clean_number('edad_usuario') }} as reported_age,
    {{ clean_timestamp('fecha_alta', 'hora_alta') }} as signed_up_at,
    case upper(trim(customer_has_dni_yes_no))
        when 'YES' then true
        when 'NO' then false
    end as has_dni,
    2025 as signup_year,
    _source_file as source_file,
    _row_number as source_row_number
from {{ source('bronze', 'users_2025') }}
