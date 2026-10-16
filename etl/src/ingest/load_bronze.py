"""Carga de los archivos de entrada a bronze (FR-01 a FR-03).

Cada archivo se carga en su propia tabla, con todas las columnas como `text` y sin transformar
valores. Además de las columnas del archivo, cada fila tiene:

- `_source_file`: nombre del archivo de origen.
- `_row_number`: posición de la fila en el archivo (1 = primera fila de datos).
- `_loaded_at`: momento de la carga.

La carga es idempotente: si el archivo tiene el mismo SHA-256 que la última carga exitosa de esa
tabla, se saltea. Si cambió, la tabla se reemplaza entera dentro de una transacción.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import psycopg
from psycopg import sql

from ingest.extract import BOM, InputFile
from ingest.log import stage

log = logging.getLogger(__name__)

SCHEMA = "bronze"
COPY_CHUNK_BYTES = 1024 * 1024
METADATA_COLUMNS = ("_source_file", "_row_number", "_loaded_at")

METADATA_DDL = """
create table if not exists bronze._ingestion_log (
    id bigint generated always as identity primary key,
    table_name text not null,
    source_file text not null,
    sha256 text not null,
    size_bytes bigint not null,
    rows_loaded bigint,
    status text not null check (status in ('loaded', 'failed')),
    error text,
    started_at timestamptz not null,
    finished_at timestamptz not null default clock_timestamp()
);
comment on table bronze._ingestion_log is 'Una fila por intento de carga de cada archivo';

create table if not exists bronze._column_mapping (
    table_name text not null,
    position integer not null,
    original_name text not null,
    column_name text not null,
    primary key (table_name, column_name)
);
comment on table bronze._column_mapping is 'Nombre original de cada columna de bronze';
"""

Mode = Literal["created", "truncated", "recreated", "skipped"]


@dataclass(frozen=True)
class LoadResult:
    table: str
    mode: Mode
    rows: int | None


def _table(name: str) -> sql.Composed:
    return sql.Identifier(SCHEMA, name)


# --------------------------------------------------------------------------------------------
# Estado en la base
# --------------------------------------------------------------------------------------------


def ensure_metadata(conn: psycopg.Connection) -> None:
    conn.execute(METADATA_DDL)


def last_loaded(conn: psycopg.Connection, table: str) -> tuple[str, int] | None:
    """(sha256, filas) de la última carga exitosa de la tabla, si existe."""
    return conn.execute(
        """
        select sha256, rows_loaded from bronze._ingestion_log
        where table_name = %s and status = 'loaded'
        order by id desc limit 1
        """,
        (table,),
    ).fetchone()


def data_columns(conn: psycopg.Connection, table: str) -> list[str] | None:
    """Columnas del archivo (sin las de metadatos) de una tabla de bronze, o None si no existe."""
    rows = conn.execute(
        """
        select column_name from information_schema.columns
        where table_schema = %s and table_name = %s
        order by ordinal_position
        """,
        (SCHEMA, table),
    ).fetchall()
    if not rows:
        return None
    return [name for (name,) in rows if name not in METADATA_COLUMNS]


def is_up_to_date(conn: psycopg.Connection, input_file: InputFile) -> bool:
    previous = last_loaded(conn, input_file.table)
    if previous is None or previous[0] != input_file.sha256:
        return False
    # La tabla tiene que seguir existiendo con las filas que se registraron.
    if data_columns(conn, input_file.table) is None:
        return False
    query = sql.SQL("select count(*) from {}").format(_table(input_file.table))
    (rows,) = conn.execute(query).fetchone()
    return rows == previous[1]


# --------------------------------------------------------------------------------------------
# Tabla destino
# --------------------------------------------------------------------------------------------


def create_table(conn: psycopg.Connection, input_file: InputFile) -> None:
    columns = [
        sql.SQL("{} text").format(sql.Identifier(column.name)) for column in input_file.columns
    ]
    columns += [
        sql.SQL("_source_file text not null default {}").format(sql.Literal(input_file.path.name)),
        sql.SQL("_row_number bigint generated always as identity"),
        sql.SQL("_loaded_at timestamptz not null default now()"),
    ]
    conn.execute(
        sql.SQL("create table {} ({})").format(
            _table(input_file.table), sql.SQL(", ").join(columns)
        )
    )


def prepare_table(conn: psycopg.Connection, input_file: InputFile) -> Mode:
    """Deja la tabla vacía y con las columnas del archivo. Si las columnas no cambiaron se
    hace truncate (no rompe las vistas de dbt que la usan); si cambiaron, se recrea."""
    existing = data_columns(conn, input_file.table)
    expected = [column.name for column in input_file.columns]
    table = _table(input_file.table)
    if existing is None:
        create_table(conn, input_file)
        return "created"
    if existing == expected:
        conn.execute(sql.SQL("truncate {} restart identity").format(table))
        conn.execute(
            sql.SQL("alter table {} alter column _source_file set default {}").format(
                table, sql.Literal(input_file.path.name)
            )
        )
        return "truncated"
    log.warning(
        "las columnas del archivo cambiaron: se recrea la tabla y las vistas que dependen de ella",
        extra={"table": input_file.table, "before": existing, "after": expected},
    )
    conn.execute(sql.SQL("drop table {} cascade").format(table))
    create_table(conn, input_file)
    return "recreated"


# --------------------------------------------------------------------------------------------
# Copia de datos
# --------------------------------------------------------------------------------------------


def copy_csv(conn: psycopg.Connection, input_file: InputFile) -> int:
    """Copia el archivo con COPY: Postgres parsea el CSV. Los vacíos quedan como '' (no NULL)
    para que bronze guarde exactamente lo que vino."""
    columns = sql.SQL(", ").join(sql.Identifier(column.name) for column in input_file.columns)
    statement = sql.SQL(
        "copy {} ({}) from stdin with "
        "(format csv, header true, delimiter {}, encoding 'UTF8', force_not_null ({}))"
    ).format(_table(input_file.table), columns, sql.Literal(input_file.delimiter), columns)
    with conn.cursor() as cursor:
        with cursor.copy(statement) as copy, input_file.path.open("rb") as file:
            head = file.read(len(BOM))
            if head != BOM:
                copy.write(head)
            while chunk := file.read(COPY_CHUNK_BYTES):
                copy.write(chunk)
        return cursor.rowcount


def geojson_rows(input_file: InputFile) -> list[list[str | None]]:
    """Una fila por feature: cada propiedad como texto y la geometría como GeoJSON."""
    data = json.loads(input_file.path.read_text(encoding="utf-8-sig"))
    rows = []
    for feature in data["features"]:
        properties = feature.get("properties") or {}
        values = [_as_text(value) for value in properties.values()]
        rows.append([*values, json.dumps(feature["geometry"], separators=(",", ":"))])
    return rows


def _as_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def copy_geojson(conn: psycopg.Connection, input_file: InputFile) -> int:
    columns = sql.SQL(", ").join(sql.Identifier(column.name) for column in input_file.columns)
    statement = sql.SQL("copy {} ({}) from stdin").format(_table(input_file.table), columns)
    rows = geojson_rows(input_file)
    with conn.cursor() as cursor, cursor.copy(statement) as copy:
        for row in rows:
            copy.write_row(row)
    return len(rows)


# --------------------------------------------------------------------------------------------
# Registro
# --------------------------------------------------------------------------------------------


def write_column_mapping(conn: psycopg.Connection, input_file: InputFile) -> None:
    conn.execute("delete from bronze._column_mapping where table_name = %s", (input_file.table,))
    with conn.cursor() as cursor:
        cursor.executemany(
            """
            insert into bronze._column_mapping (table_name, position, original_name, column_name)
            values (%s, %s, %s, %s)
            """,
            [
                (input_file.table, position, column.original, column.name)
                for position, column in enumerate(input_file.columns, start=1)
            ],
        )


def log_ingestion(
    conn: psycopg.Connection,
    input_file: InputFile,
    started_at: datetime,
    status: str,
    rows: int | None = None,
    error: str | None = None,
) -> None:
    conn.execute(
        """
        insert into bronze._ingestion_log
            (table_name, source_file, sha256, size_bytes, rows_loaded, status, error, started_at)
        values (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            input_file.table,
            input_file.path.name,
            input_file.sha256,
            input_file.size_bytes,
            rows,
            status,
            error,
            started_at,
        ),
    )


# --------------------------------------------------------------------------------------------
# Orquestación
# --------------------------------------------------------------------------------------------


def load_file(conn: psycopg.Connection, input_file: InputFile, force: bool = False) -> LoadResult:
    fields = {"table": input_file.table, "file": input_file.path.name}
    if not force and is_up_to_date(conn, input_file):
        log.info("sin cambios desde la última carga: se saltea", extra=fields)
        return LoadResult(input_file.table, "skipped", None)

    started_at = datetime.now(UTC)
    with stage(log, "load_bronze", **fields) as result:
        try:
            with conn.transaction():
                mode = prepare_table(conn, input_file)
                copy = copy_geojson if input_file.source.kind == "geojson" else copy_csv
                rows = copy(conn, input_file)
                write_column_mapping(conn, input_file)
                log_ingestion(conn, input_file, started_at, "loaded", rows=rows)
        except psycopg.Error as error:
            # La transacción se deshizo; el intento fallido queda registrado aparte.
            log_ingestion(conn, input_file, started_at, "failed", error=str(error).strip())
            raise
        result.update(mode=mode, rows=rows)
    return LoadResult(input_file.table, mode, rows)


def load_all(conninfo: str, inputs: list[InputFile], force: bool = False) -> list[LoadResult]:
    with psycopg.connect(conninfo, autocommit=True) as conn:
        ensure_metadata(conn)
        return [load_file(conn, input_file, force=force) for input_file in inputs]
