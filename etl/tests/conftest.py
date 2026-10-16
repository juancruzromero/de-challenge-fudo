"""Fixtures compartidas.

Los tests marcados `integration` usan el Postgres del stack (make up): cada sesión crea una base
temporal `ecobici_test_<id>` con el schema bronze y la borra al terminar, así nunca tocan los
datos reales. Si Postgres no responde, esos tests se saltean.

Conexión: TEST_PG_HOST (localhost), POSTGRES_HOST_PORT (5432), POSTGRES_USER y POSTGRES_PASSWORD,
que `make test` toma de .env.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo


def _admin_conninfo(dbname: str = "postgres") -> str:
    return make_conninfo(
        host=os.environ.get("TEST_PG_HOST", "localhost"),
        port=os.environ.get("POSTGRES_HOST_PORT", "5432"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
        dbname=dbname,
        connect_timeout=3,
    )


@pytest.fixture(scope="session")
def test_database() -> Iterator[str]:
    """Conninfo de una base temporal con el schema bronze."""
    name = f"ecobici_test_{uuid.uuid4().hex[:8]}"
    try:
        admin = psycopg.connect(_admin_conninfo(), autocommit=True)
    except psycopg.OperationalError as error:
        pytest.skip(f"Postgres no disponible para tests de integración (make up): {error}")
    with admin:
        admin.execute(sql.SQL("create database {}").format(sql.Identifier(name)))
    conninfo = _admin_conninfo(name)
    try:
        with psycopg.connect(conninfo, autocommit=True) as conn:
            conn.execute("create schema bronze")
        yield conninfo
    finally:
        with psycopg.connect(_admin_conninfo(), autocommit=True) as admin:
            admin.execute(
                sql.SQL("drop database if exists {} with (force)").format(sql.Identifier(name))
            )


@pytest.fixture
def db(test_database: str) -> Iterator[psycopg.Connection]:
    """Conexión a la base temporal; vacía bronze antes de cada test."""
    with psycopg.connect(test_database, autocommit=True) as conn:
        conn.execute("drop schema bronze cascade")
        conn.execute("create schema bronze")
        yield conn
