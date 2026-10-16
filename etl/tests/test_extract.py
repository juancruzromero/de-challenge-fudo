import hashlib
import json
import logging
from pathlib import Path

import pytest

from ingest.extract import (
    SOURCES,
    InputError,
    Source,
    discover,
    geojson_header,
    inspect_csv,
    normalize_column,
    normalize_header,
    sha256_file,
    validate_identifier,
)

BOM = b"\xef\xbb\xbf"


def write(path: Path, text: str, bom: bool = False) -> Path:
    path.write_bytes((BOM if bom else b"") + text.encode("utf-8"))
    return path


def feature(**properties) -> dict:
    return {"type": "Feature", "properties": properties, "geometry": {"type": "Point"}}


# --- nombres de columna ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("original", "expected"),
    [
        ("ID Cliente", "id_cliente"),
        ("género", "genero"),
        ("Customer Has Dni (Yes / No)", "customer_has_dni_yes_no"),
        ("Id_recorrido", "id_recorrido"),
        ("  long_estacion_origen ", "long_estacion_origen"),
        ("Año 2025", "ano_2025"),
        ("2025 viajes", "c_2025_viajes"),
    ],
)
def test_normalize_column(original, expected):
    assert normalize_column(original) == expected


def test_normalize_column_rejects_names_without_letters_or_digits():
    with pytest.raises(InputError, match="vacía"):
        normalize_column("(?)")


def test_normalize_header_keeps_original_names():
    columns = normalize_header(["ID Cliente", "género"])

    assert [(c.original, c.name) for c in columns] == [
        ("ID Cliente", "id_cliente"),
        ("género", "genero"),
    ]


def test_normalize_header_rejects_collisions():
    with pytest.raises(InputError, match="mismo nombre"):
        normalize_header(["Género", "genero"])


@pytest.mark.parametrize("name", ["trips; drop table x", "Trips", "1trips", ""])
def test_validate_identifier_rejects_unsafe_names(name):
    with pytest.raises(InputError):
        validate_identifier(name)


# --- archivos -------------------------------------------------------------------------------


def test_sha256_file_matches_hashlib(tmp_path):
    path = write(tmp_path / "x.csv", "a,b\n1,2\n")

    assert sha256_file(path) == hashlib.sha256(path.read_bytes()).hexdigest()


def test_inspect_csv_strips_bom_and_detects_delimiter(tmp_path):
    path = write(tmp_path / "x.csv", "id;nombre\n1;Retiro\n", bom=True)

    assert inspect_csv(path) == (True, ";", ["id", "nombre"])


def test_inspect_csv_handles_quoted_commas(tmp_path):
    path = write(tmp_path / "x.csv", 'id,direccion\n1,"3024 Calvo, Carlos"\n')

    assert inspect_csv(path) == (False, ",", ["id", "direccion"])


def test_inspect_csv_rejects_empty_files(tmp_path):
    with pytest.raises(InputError, match="vacío"):
        inspect_csv(write(tmp_path / "x.csv", "\n"))


def test_geojson_header_lists_properties_and_geometry(tmp_path):
    path = tmp_path / "c.geojson"
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": [feature(id=1, comuna=1)] * 2})
    )

    assert geojson_header(path) == ["id", "comuna", "geometry"]


def test_geojson_header_rejects_inconsistent_properties(tmp_path):
    path = tmp_path / "c.geojson"
    features = [feature(id=1), feature(id=2, extra=True)]
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))

    with pytest.raises(InputError, match="feature 1"):
        geojson_header(path)


# --- discover -------------------------------------------------------------------------------


@pytest.fixture
def data_dirs(tmp_path):
    raw, reference = tmp_path / "raw", tmp_path / "reference"
    raw.mkdir()
    reference.mkdir()
    write(raw / "usuarios.csv", "ID Cliente,género\n1,MALE\n", bom=True)
    collection = {"type": "FeatureCollection", "features": [feature(comuna=1)]}
    (reference / "comunas.geojson").write_text(json.dumps(collection))
    return raw, reference


SMALL_SOURCES = (
    Source("comunas", "comunas.geojson", kind="geojson", location="reference"),
    Source("users", "usuarios.csv"),
)


def test_discover_inspects_every_source(data_dirs):
    inputs = discover(*data_dirs, sources=SMALL_SOURCES)

    comunas, users = inputs
    assert [c.name for c in comunas.columns] == ["comuna", "geometry"]
    assert comunas.delimiter is None
    assert users.table == "users"
    assert users.has_bom is True
    assert [c.name for c in users.columns] == ["id_cliente", "genero"]
    assert len(users.sha256) == 64


def test_discover_lists_all_missing_files(data_dirs):
    sources = (*SMALL_SOURCES, Source("a", "a.csv"), Source("b", "b.csv"))

    with pytest.raises(InputError, match=r"a\.csv.*b\.csv"):
        discover(*data_dirs, sources=sources)


def test_discover_warns_about_unexpected_files(data_dirs, caplog):
    raw, _ = data_dirs
    write(raw / "otro.csv", "x\n1\n")
    write(raw / "ecobici-datasets-2025.zip", "zip")

    with caplog.at_level(logging.WARNING):
        discover(*data_dirs, sources=SMALL_SOURCES)

    assert [r.files for r in caplog.records if r.levelno == logging.WARNING] == [["otro.csv"]]


def test_sources_have_unique_tables_and_files():
    assert len({s.table for s in SOURCES}) == len(SOURCES)
    assert len({s.file for s in SOURCES}) == len(SOURCES)
