# Entrypoints del proyecto. `make` o `make help` lista los comandos.
# Compatible con GNU Make 3.81 (el que trae macOS).

COMPOSE := docker compose
UV      := uv run --project etl

# Variables de .env disponibles en los comandos (POSTGRES_USER, BI_DB_USER, ...).
-include .env
export

.DEFAULT_GOAL := help
.PHONY: help env up down reset ps logs psql etl dbt sql setup test lint profile

help: ## Lista los comandos disponibles
	@echo "Uso: make <comando>"
	@echo
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

# --- Stack ----------------------------------------------------------------------------------

env: ## Crea .env desde .env.example si no existe
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Creado .env desde .env.example (valores de ejemplo para local)."; \
	fi

up: env ## Levanta todo el stack y espera a que esté healthy
	$(COMPOSE) up -d --build --wait
	@echo
	@echo "Metabase:   http://localhost:$${METABASE_PORT:-3000}"
	@echo "PostgreSQL: localhost:$${POSTGRES_HOST_PORT:-5432} (make psql)"

down: ## Detiene el stack (conserva los datos)
	$(COMPOSE) down

reset: ## Borra los volúmenes y vuelve a levantar desde cero (FORCE=1 para no preguntar)
	@if [ "$(FORCE)" != "1" ]; then \
		printf "Esto borra la base y la configuración de Metabase. ¿Seguir? [y/N] "; \
		read answer; [ "$$answer" = "y" ] || { echo "Cancelado."; exit 1; }; \
	fi
	$(COMPOSE) down -v
	@$(MAKE) up

ps: ## Estado de los servicios
	$(COMPOSE) ps

logs: ## Logs en vivo (s=<servicio> para uno solo, ej. make logs s=postgres)
	$(COMPOSE) logs -f $(s)

psql: env ## Consola SQL en la base analítica como superusuario
	$(COMPOSE) exec postgres psql -U "$(POSTGRES_USER)" -d "$(POSTGRES_DB)"

# --- Pipeline -------------------------------------------------------------------------------

# Corta con un mensaje claro si el servicio todavía no está en docker-compose.yml.
define require_service
	@$(COMPOSE) config --services 2>/dev/null | grep -qx $(1) || { \
		echo "El servicio '$(1)' todavía no existe: se agrega en $(2) (ver specs/tasks.md)."; \
		exit 1; }
endef

etl: env ## Corre el pipeline completo: ingesta a bronze + dbt build
	$(call require_service,etl,T3.4)
	$(COMPOSE) run --rm etl

dbt: env ## Corre un comando de dbt (c="build --select silver", por defecto build)
	$(call require_service,etl,T3.4)
	$(COMPOSE) run --rm etl dbt $(or $(c),build)

sql: env ## Corre las consultas de sql/analysis/ como bi_reader
	@ls sql/analysis/*.sql >/dev/null 2>&1 || { \
		echo "Todavía no hay consultas en sql/analysis/: se agregan en T5.5."; exit 1; }
	@for file in sql/analysis/*.sql; do \
		echo "=== $$file"; \
		$(COMPOSE) exec -T -e PGPASSWORD="$(BI_DB_PASSWORD)" postgres \
			psql -h localhost -U "$(BI_DB_USER)" -d "$(POSTGRES_DB)" -v ON_ERROR_STOP=1 \
			< "$$file" || exit 1; \
	done

# --- Desarrollo local -----------------------------------------------------------------------

setup: ## Instala el entorno local (uv) y los hooks de pre-commit
	uv sync --project etl
	$(UV) pre-commit install

test: ## Corre los tests de Python (los de integración necesitan make up)
	uv run --directory etl pytest $(args)

lint: ## Corre todos los hooks de pre-commit (ruff, sqlfluff, ...)
	$(UV) pre-commit run --all-files

profile: ## Regenera docs/profiling/profile.md desde data/raw/
	$(UV) ecobici-profile
