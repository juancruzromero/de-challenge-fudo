"""Provisión de Metabase por API (T7.1).

Deja Metabase listo sin pasos manuales: crea el usuario admin (si la instancia está sin
configurar), quita el contenido de ejemplo, conecta la base analítica como `bi_reader` mostrando
solo el schema gold, y espera a que Metabase sincronice las tablas. Es idempotente: se puede
correr las veces que haga falta.

Solo usa la librería estándar, para correr en una imagen de Python sin instalar nada.

Uso: lo corre el servicio `metabase-provision` de docker compose (`make provision` para repetir).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field

log = logging.getLogger("provision")

DATABASE_NAME = "Ecobici BA 2025"
SITE_NAME = "Ecobici BA 2025"
# Tablas que tienen que estar sincronizadas para dar la provisión por terminada.
EXPECTED_TABLES = frozenset({"fct_trips", "agg_station_od_monthly", "dim_station"})


class ProvisionError(RuntimeError):
    """La provisión no pudo completarse."""


class MetabaseError(ProvisionError):
    def __init__(self, method: str, path: str, status: int, body: str):
        super().__init__(f"{method} {path} respondió {status}: {body[:300]}")
        self.status = status


@dataclass(frozen=True)
class Settings:
    url: str
    admin_email: str
    admin_password: str = field(repr=False)
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str = field(repr=False)
    timeout_s: int = 300

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if environ is None else environ
        required = (
            "MB_ADMIN_EMAIL",
            "MB_ADMIN_PASSWORD",
            "POSTGRES_DB",
            "BI_DB_USER",
            "BI_DB_PASSWORD",
        )
        missing = [name for name in required if not env.get(name, "").strip()]
        if missing:
            raise ProvisionError(f"Faltan variables de entorno: {', '.join(missing)}")
        url = env.get("MB_URL", "http://metabase:3000").strip().rstrip("/")
        if not url.startswith(("http://", "https://")):
            raise ProvisionError(f"MB_URL debe empezar con http:// o https://, no {url!r}")
        return cls(
            url=url,
            admin_email=env["MB_ADMIN_EMAIL"].strip(),
            admin_password=env["MB_ADMIN_PASSWORD"],
            db_host=env.get("POSTGRES_HOST", "postgres").strip(),
            db_port=int(env.get("POSTGRES_PORT", "5432")),
            db_name=env["POSTGRES_DB"].strip(),
            db_user=env["BI_DB_USER"].strip(),
            db_password=env["BI_DB_PASSWORD"],
            timeout_s=int(env.get("MB_PROVISION_TIMEOUT", "300")),
        )


class MetabaseClient:
    """Cliente mínimo de la API de Metabase: JSON de ida y vuelta, con sesión."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session_id: str | None = None

    def request(self, method: str, path: str, body: object | None = None) -> object:
        data = None if body is None else json.dumps(body).encode()
        # S310: base_url se valida en Settings.from_env (solo http/https).
        req = urllib.request.Request(self.base_url + path, data=data, method=method)  # noqa: S310
        req.add_header("Content-Type", "application/json")
        if self.session_id:
            req.add_header("X-Metabase-Session", self.session_id)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:  # noqa: S310
                raw = response.read()
        except urllib.error.HTTPError as error:
            body_text = error.read().decode(errors="replace")
            raise MetabaseError(method, path, error.code, body_text) from error
        return json.loads(raw) if raw else None

    def get(self, path: str) -> object:
        return self.request("GET", path)

    def post(self, path: str, body: object | None = None) -> object:
        return self.request("POST", path, body)

    def put(self, path: str, body: object) -> object:
        return self.request("PUT", path, body)


# --------------------------------------------------------------------------------------------
# Pasos
# --------------------------------------------------------------------------------------------


def wait_until_healthy(client: MetabaseClient, timeout_s: int, sleep=time.sleep) -> None:
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            if (client.get("/api/health") or {}).get("status") == "ok":
                return
        except (OSError, MetabaseError):
            pass  # todavía arrancando
        if time.monotonic() >= deadline:
            raise ProvisionError(f"Metabase no respondió healthy en {timeout_s} s")
        log.info("Esperando a que Metabase esté healthy...")
        sleep(5)


def ensure_admin(client: MetabaseClient, settings: Settings) -> bool:
    """Crea el admin en una instancia sin configurar. Devuelve True si lo creó."""
    properties = client.get("/api/session/properties")
    if properties.get("has-user-setup"):
        log.info("Metabase ya tiene usuario admin: se omite el setup")
        return False
    client.post(
        "/api/setup",
        {
            "token": properties["setup-token"],
            "user": {
                "email": settings.admin_email,
                "password": settings.admin_password,
                "first_name": "Admin",
                "last_name": "Ecobici",
                "site_name": SITE_NAME,
            },
            "prefs": {"site_name": SITE_NAME, "site_locale": "es", "allow_tracking": False},
        },
    )
    log.info("Usuario admin creado: %s", settings.admin_email)
    return True


def login(client: MetabaseClient, settings: Settings) -> None:
    try:
        session = client.post(
            "/api/session",
            {"username": settings.admin_email, "password": settings.admin_password},
        )
    except MetabaseError as error:
        if error.status in (400, 401):
            raise ProvisionError(
                "No se pudo iniciar sesión con MB_ADMIN_EMAIL/MB_ADMIN_PASSWORD. Si cambiaste "
                "las credenciales después del primer arranque, volvé a las originales o borrá "
                "la configuración de Metabase con make reset."
            ) from error
        raise
    client.session_id = session["id"]


def database_payload(settings: Settings) -> dict:
    return {
        "engine": "postgres",
        "name": DATABASE_NAME,
        "details": {
            "host": settings.db_host,
            "port": settings.db_port,
            "dbname": settings.db_name,
            "user": settings.db_user,
            "password": settings.db_password,
            "ssl": False,
            # bi_reader solo puede leer gold; el filtro evita que Metabase liste schemas vacíos.
            "schema-filters-type": "inclusion",
            "schema-filters-patterns": "gold",
        },
        "is_full_sync": True,
    }


def list_databases(client: MetabaseClient) -> list[dict]:
    response = client.get("/api/database")
    # Según la versión, la API devuelve la lista directa o envuelta en {"data": [...]}.
    return response["data"] if isinstance(response, dict) else response


def ensure_database(client: MetabaseClient, settings: Settings) -> int:
    """Crea la conexión a la base analítica o la actualiza si ya existe. Devuelve su ID."""
    payload = database_payload(settings)
    existing = next((d for d in list_databases(client) if d["name"] == DATABASE_NAME), None)
    if existing:
        client.put(f"/api/database/{existing['id']}", payload)
        log.info("Conexión '%s' actualizada (id %s)", DATABASE_NAME, existing["id"])
        return existing["id"]
    created = client.post("/api/database", payload)
    log.info("Conexión '%s' creada (id %s)", DATABASE_NAME, created["id"])
    return created["id"]


def remove_sample_content(client: MetabaseClient) -> None:
    """Borra la base de ejemplo y archiva la colección "Examples".

    MB_LOAD_SAMPLE_CONTENT=false los evita en una instalación nueva, pero no en una instancia
    cuya base interna ya existía. Así solo queda la conexión a Ecobici."""
    for database in list_databases(client):
        if database.get("is_sample"):
            client.request("DELETE", f"/api/database/{database['id']}")
            log.info("Base de ejemplo '%s' eliminada", database["name"])
    items = client.get("/api/collection/root/items?models=collection")
    for item in items["data"] if isinstance(items, dict) else items:
        if item.get("name") == "Examples":
            client.put(f"/api/collection/{item['id']}", {"archived": True})
            log.info("Colección de ejemplo 'Examples' archivada")


def synced_tables(client: MetabaseClient, database_id: int) -> set[str]:
    metadata = client.get(f"/api/database/{database_id}/metadata")
    return {table["name"] for table in metadata.get("tables", []) if table.get("schema") == "gold"}


def wait_for_sync(
    client: MetabaseClient, database_id: int, timeout_s: int, sleep=time.sleep
) -> set[str]:
    client.post(f"/api/database/{database_id}/sync_schema")
    deadline = time.monotonic() + timeout_s
    while True:
        tables = synced_tables(client, database_id)
        missing = EXPECTED_TABLES - tables
        if not missing:
            log.info("Sincronizadas %d tablas de gold", len(tables))
            return tables
        if time.monotonic() >= deadline:
            raise ProvisionError(f"Metabase no sincronizó {sorted(missing)} en {timeout_s} s")
        log.info("Esperando la sincronización (faltan %s)...", ", ".join(sorted(missing)))
        sleep(5)


def provision(client: MetabaseClient, settings: Settings) -> int:
    wait_until_healthy(client, settings.timeout_s)
    ensure_admin(client, settings)
    login(client, settings)
    remove_sample_content(client)
    database_id = ensure_database(client, settings)
    wait_for_sync(client, database_id, settings.timeout_s)
    return database_id


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        settings = Settings.from_env()
        provision(MetabaseClient(settings.url), settings)
    except ProvisionError as error:
        log.error("%s", error)
        return 1
    log.info("Metabase listo en %s", os.environ.get("MB_PUBLIC_URL", settings.url))
    return 0


if __name__ == "__main__":
    sys.exit(main())
