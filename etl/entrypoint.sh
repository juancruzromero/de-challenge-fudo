#!/bin/sh
# Sin argumentos: corre el pipeline completo (ingesta a bronze + dbt build).
# Con argumentos: ejecuta ese comando, por ejemplo `docker compose run --rm etl dbt test`.
set -eu

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

ecobici-ingest

# DBT_PROJECT_DIR y DBT_PROFILES_DIR vienen de la imagen (etl/Dockerfile).
exec dbt build
