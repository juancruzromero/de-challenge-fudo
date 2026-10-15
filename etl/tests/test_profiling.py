from pathlib import Path

import pytest

from profiling.datasets import DatasetSpec, DateRule, NumericRule
from profiling.profile import (
    coverage,
    detect_format,
    fmt_pct,
    haversine_m,
    normalize_id,
    parse_number,
    point_in_geometry,
    profile_dataset,
    render_dataset,
)

SQUARE = {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]}
SQUARE_WITH_HOLE = {
    "type": "Polygon",
    "coordinates": [
        [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
        [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]],
    ],
}


def write_csv(path: Path, text: str, bom: bool = False) -> Path:
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))
    return path


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("146BAEcobici", "146"), ("1.0", "1"), (" 7 ", "7"), ("1473152", "1473152")],
)
def test_normalize_id(raw, expected):
    assert normalize_id(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("800", (800.0, False)),
        ("3,108", (3108.0, True)),
        ("-58.4", (-58.4, False)),
        ("abc", (None, False)),
    ],
)
def test_parse_number(raw, expected):
    assert parse_number(raw) == expected


def test_detect_format_reads_bom_delimiter_and_header(tmp_path):
    path = write_csv(tmp_path / "x.csv", "id;nombre\n1;Retiro\n2;Aduana\n", bom=True)

    fmt = detect_format(path)

    assert fmt.has_bom is True
    assert fmt.delimiter == ";"
    assert fmt.header == ["id", "nombre"]


def test_point_in_geometry_respects_holes():
    assert point_in_geometry(1, 1, SQUARE)
    assert not point_in_geometry(11, 1, SQUARE)
    assert not point_in_geometry(5, 5, SQUARE_WITH_HOLE)
    assert point_in_geometry(1, 1, {"type": "MultiPolygon", "coordinates": [SQUARE["coordinates"]]})


def test_haversine_one_degree_of_latitude_is_about_111_km():
    assert haversine_m(-34.0, -58.0, -35.0, -58.0) == pytest.approx(111_195, rel=1e-3)


def test_coverage_counts_keys_and_weights():
    result = coverage("x", {"1": 5, "2": 3, "9": 2}, {"1", "2"})

    assert (result.matched_keys, result.total_keys) == (2, 3)
    assert (result.matched_weight, result.total_weight) == (8, 10)
    assert result.missing == [("9", 2)]


def test_fmt_pct_uses_spanish_decimal_comma():
    assert fmt_pct(1, 3) == "33,3 %"


def test_profile_dataset_end_to_end(tmp_path):
    path = write_csv(
        tmp_path / "trips.csv",
        "id,duracion,fecha,modelo,id_est,nombre_est\n"
        "1,800,2025-01-10 08:00:00,FIT,10BAEcobici,Retiro\n"
        '2,"3,108",2025-02-10 08:00:00,ICONIC,10BAEcobici,RETIRO II\n'
        "2,90000,2024-12-31 23:00:00,,11BAEcobici,Aduana\n",
    )
    spec = DatasetSpec(
        name="trips",
        title="Viajes",
        file="trips.csv",
        unique=("id",),
        numeric=(NumericRule("duracion", min_value=1, max_value=86_400),),
        dates=(DateRule("fecha", year=2025, monthly=True),),
        categorical=("modelo",),
        keys={"station": ("id_est",)},
        consistency={"estación con más de un nombre": (("id_est", "nombre_est"),)},
        row_checks={"duración larga": lambda row: row["duracion"] == "90000"},
    )

    profile = profile_dataset(path, spec)

    assert profile.rows == 3
    assert profile.duplicates == {"id": 1}
    assert profile.columns["modelo"].empty == 1
    duration = profile.numeric["duracion"]
    assert (duration.min_value, duration.max_value) == (800, 90_000)
    assert (duration.with_separator, duration.above) == (1, 1)
    assert profile.dates["fecha"].out_of_year == 1
    assert profile.keys["station"] == {"10": 2, "11": 1}
    assert profile.inconsistent == {"estación con más de un nombre": ["10"]}
    assert profile.row_checks["duración larga"] == 1
    assert "## Viajes — `trips.csv`" in render_dataset(profile)


def test_profile_dataset_fails_on_missing_columns(tmp_path):
    path = write_csv(tmp_path / "x.csv", "a,b\n1,2\n")
    spec = DatasetSpec(name="x", title="X", file="x.csv", unique=("id",))

    with pytest.raises(ValueError, match="faltan columnas"):
        profile_dataset(path, spec)


def test_duplicates_ignore_empty_values(tmp_path):
    path = write_csv(tmp_path / "x.csv", "id,nombre\n1,a\n,b\n,c\n1,d\n")
    spec = DatasetSpec(name="x", title="X", file="x.csv", unique=("id",))

    profile = profile_dataset(path, spec)

    assert profile.duplicates == {"id": 1}
    assert profile.columns["id"].empty == 2
