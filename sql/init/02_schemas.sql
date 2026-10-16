-- Un schema por capa de la arquitectura medallion (plan.md §4).
create schema if not exists bronze;
comment on schema bronze is 'CSV crudos tal cual llegan, columnas text + metadatos de carga';

create schema if not exists silver;
comment on schema silver is 'Datos tipados, normalizados y deduplicados; rechazos en *_rejected';

create schema if not exists gold;
comment on schema gold is 'Modelo estrella, agregados y marts analíticos; lo consume Metabase';
