# Imagen del ETL: ingesta a bronze (Python) + transformaciones (dbt, desde T4.1).
# Se construye desde la raíz del repo: docker compose build etl
FROM python:3.12.15-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app

# 1. Dependencias: cambian poco, quedan en una capa cacheada.
COPY etl/pyproject.toml etl/uv.lock etl/.python-version etl/
RUN uv sync --project etl --frozen --no-dev --no-install-project

# 2. Código del ETL.
COPY etl/src etl/src
RUN uv sync --project etl --frozen --no-dev

# 3. Proyecto dbt (se agrega en T4.1; el entrypoint lo saltea si no existe).
COPY dbt dbt

COPY etl/entrypoint.sh /usr/local/bin/entrypoint.sh

RUN useradd --create-home --uid 10001 etl && chown -R etl /app
USER etl

ENTRYPOINT ["entrypoint.sh"]
