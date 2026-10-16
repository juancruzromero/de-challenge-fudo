#!/usr/bin/env bash
# Roles de la base analítica. Es un script de shell (no .sql) porque las contraseñas vienen
# del entorno (.env) y se pasan a psql como variables, sin escribirlas en ningún archivo.
#
#   etl        dueño de bronze, silver y gold: la ingesta y dbt crean y reemplazan tablas.
#   bi_reader  solo lectura sobre gold: es el usuario con el que se conecta Metabase.
set -euo pipefail

psql -v ON_ERROR_STOP=1 \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --set db="$POSTGRES_DB" \
    --set etl_user="$ETL_DB_USER" \
    --set etl_password="$ETL_DB_PASSWORD" \
    --set bi_user="$BI_DB_USER" \
    --set bi_password="$BI_DB_PASSWORD" <<'SQL'
-- Crear los roles solo si no existen (\gexec ejecuta el SQL generado).
select format('create role %I login password %L', :'etl_user', :'etl_password')
where not exists (select 1 from pg_roles where rolname = :'etl_user')
\gexec
select format('create role %I login password %L', :'bi_user', :'bi_password')
where not exists (select 1 from pg_roles where rolname = :'bi_user')
\gexec

-- Nadie se conecta salvo los roles explícitos.
revoke all on database :"db" from public;
grant connect, temporary on database :"db" to :"etl_user";
grant connect on database :"db" to :"bi_user";

-- etl es dueño de las tres capas.
alter schema bronze owner to :"etl_user";
alter schema silver owner to :"etl_user";
alter schema gold owner to :"etl_user";

-- bi_reader lee gold, incluidas las tablas que etl cree más adelante.
grant usage on schema gold to :"bi_user";
grant select on all tables in schema gold to :"bi_user";
alter default privileges for role :"etl_user" in schema gold
    grant select on tables to :"bi_user";
SQL

echo "Roles ${ETL_DB_USER} y ${BI_DB_USER} listos."
