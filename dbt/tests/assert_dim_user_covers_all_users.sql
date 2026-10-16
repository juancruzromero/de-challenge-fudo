-- dim_user = usuarios con perfil ∪ usuarios de los viajes (ADR 003).
-- El test falla si devuelve filas: usuarios de users o de trips que no están en dim_user, o
-- usuarios de dim_user que no salen de ninguno de los dos.
with expected as (
    select user_id from {{ ref('users') }}
    union
    select user_id from {{ ref('trips') }}
)

select
    coalesce(expected.user_id, dim_user.user_id) as user_id,
    case
        when dim_user.user_id is null then 'missing_in_dim_user'
        else 'unexpected_in_dim_user'
    end as problem
from expected
full outer join {{ ref('dim_user') }} as dim_user
    on expected.user_id = dim_user.user_id
where expected.user_id is null or dim_user.user_id is null
