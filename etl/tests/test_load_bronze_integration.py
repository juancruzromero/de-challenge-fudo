"""Carga a bronze contra un Postgres real (base temporal, ver conftest.py)."""

import json
from pathlib import Path

import psycopg
import pytest

from ingest.extract import Source, inspect_source
from ingest.load_bronze import ensure_metadata, load_file

pytestmark = pytest.mark.integration

BOM = b"\xef\xbb\xbf"
USERS_CSV = (
    'ID Cliente,género,dirección\n1,MALE,"3024 Calvo, Carlos"\n2,,Av. Cerviño 4301\n3,"3,108",""\n'
)


def write(path: Path, text: str, bom: bool = False) -> Path:
    path.write_bytes((BOM if bom else b"") + text.encode("utf-8"))
    return path


def users_file(tmp_path: Path, text: str = USERS_CSV, bom: bool = True):
    path = write(tmp_path / "usuarios.csv", text, bom=bom)
    return inspect_source(Source("users", path.name), path)


def rows(db: psycopg.Connection, query: str) -> list[tuple]:
    return db.execute(query).fetchall()


@pytest.fixture
def loader(db):
    ensure_metadata(db)
    return lambda input_file, force=False: load_file(db, input_file, force=force)


def test_first_load_creates_table_with_metadata_and_raw_values(db, loader, tmp_path):
    result = loader(users_file(tmp_path))

    assert (result.mode, result.rows) == ("created", 3)
    assert rows(
        db, "select _row_number, id_cliente, genero, direccion, _source_file from bronze.users"
    ) == [
        (1, "1", "MALE", "3024 Calvo, Carlos", "usuarios.csv"),
        (2, "2", "", "Av. Cerviño 4301", "usuarios.csv"),  # vacío -> '' (no NULL)
        (3, "3", "3,108", "", "usuarios.csv"),  # coma dentro de comillas
    ]
    assert rows(db, "select count(*) from bronze.users where _loaded_at is null") == [(0,)]


def test_column_mapping_keeps_original_names(db, loader, tmp_path):
    loader(users_file(tmp_path))

    assert rows(
        db,
        "select position, original_name, column_name from bronze._column_mapping order by 1",
    ) == [(1, "ID Cliente", "id_cliente"), (2, "género", "genero"), (3, "dirección", "direccion")]


def test_second_load_of_same_file_is_skipped(db, loader, tmp_path):
    input_file = users_file(tmp_path)
    loader(input_file)

    result = loader(input_file)

    assert result.mode == "skipped"
    assert rows(db, "select count(*) from bronze.users") == [(3,)]
    assert rows(db, "select status, count(*) from bronze._ingestion_log group by 1") == [
        ("loaded", 1)
    ]


def test_force_reloads_same_file(db, loader, tmp_path):
    input_file = users_file(tmp_path)
    loader(input_file)

    result = loader(input_file, force=True)

    assert (result.mode, result.rows) == ("truncated", 3)
    assert rows(db, "select min(_row_number), max(_row_number) from bronze.users") == [(1, 3)]


def test_changed_file_with_same_columns_is_truncated_and_reloaded(db, loader, tmp_path):
    loader(users_file(tmp_path))

    result = loader(users_file(tmp_path, "ID Cliente,género,dirección\n9,OTHER,x\n"))

    assert (result.mode, result.rows) == ("truncated", 1)
    assert rows(db, "select _row_number, id_cliente from bronze.users") == [(1, "9")]


def test_changed_columns_recreate_the_table(db, loader, tmp_path):
    loader(users_file(tmp_path))

    result = loader(users_file(tmp_path, "id_usuario,edad\n7,30\n"))

    assert result.mode == "recreated"
    assert rows(db, "select id_usuario, edad from bronze.users") == [("7", "30")]


def test_table_dropped_by_hand_is_reloaded(db, loader, tmp_path):
    input_file = users_file(tmp_path)
    loader(input_file)
    db.execute("drop table bronze.users")

    assert loader(input_file).mode == "created"


def test_broken_file_rolls_back_and_logs_the_failure(db, loader, tmp_path):
    loader(users_file(tmp_path))
    broken = users_file(tmp_path, USERS_CSV + "4,MALE,x,columna de más\n")

    with pytest.raises(psycopg.errors.BadCopyFileFormat):
        loader(broken)

    assert rows(db, "select count(*) from bronze.users") == [(3,)]
    status, error = rows(
        db, "select status, error from bronze._ingestion_log order by id desc limit 1"
    )[0]
    assert status == "failed"
    assert "extra data after last expected column" in error
    # El archivo bueno sigue registrado como la última carga exitosa.
    assert loader(users_file(tmp_path)).mode == "skipped"


def test_geojson_is_loaded_one_row_per_feature(db, loader, tmp_path):
    geometry = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}
    features = [
        {"type": "Feature", "properties": {"comuna": n, "barrios": "Retiro"}, "geometry": geometry}
        for n in (1, 2)
    ]
    path = tmp_path / "comunas.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))

    result = loader(inspect_source(Source("comunas", path.name, kind="geojson"), path))

    assert (result.mode, result.rows) == ("created", 2)
    assert rows(db, "select comuna, barrios from bronze.comunas order by 1") == [
        ("1", "Retiro"),
        ("2", "Retiro"),
    ]
    (geometry_text,) = rows(db, "select geometry from bronze.comunas limit 1")[0]
    assert json.loads(geometry_text) == geometry
