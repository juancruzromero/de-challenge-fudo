-- Usuarios descartados por las reglas de calidad (FR-08), con el motivo y la fila de origen
-- para poder rastrearlos en bronze.
select
    reject_reason,
    source_file,
    source_row_number,
    user_id,
    gender,
    reported_age,
    signed_up_at,
    has_dni,
    signup_year
from {{ ref('users_validated') }}
where reject_reason is not null
