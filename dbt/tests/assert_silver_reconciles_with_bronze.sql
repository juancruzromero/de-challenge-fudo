-- Toda fila de bronze termina en silver o en *_rejected (spec.md §6).
-- El test falla si devuelve filas: entidades donde bronze <> silver + rechazados.
select
    entity,
    bronze_rows,
    silver_rows,
    rejected_rows,
    difference
from {{ ref('reconciliation') }}
where difference <> 0
