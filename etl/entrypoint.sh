#!/bin/sh
# Sin argumentos: corre el pipeline completo (ingesta a bronze + dbt build).
# Con argumentos: ejecuta ese comando, por ejemplo `docker compose run --rm etl dbt test`.
set -eu

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

ecobici-ingest

if [ -f /app/dbt/dbt_project.yml ]; then
    exec dbt build --project-dir /app/dbt --profiles-dir /app/dbt
fi
echo "dbt todavía no está configurado (T4.1): se saltea dbt build."
