import json

from ingest.extract import Source, inspect_source
from ingest.load_bronze import _as_text, geojson_rows


def test_as_text_keeps_text_and_serializes_the_rest():
    assert _as_text(None) is None
    assert _as_text("Retiro, Recoleta") == "Retiro, Recoleta"
    assert _as_text(36011.96) == "36011.96"
    assert _as_text({"a": "ñ"}) == '{"a": "ñ"}'


def test_geojson_rows_has_one_row_per_feature_with_geometry_last(tmp_path):
    geometry = {"type": "Point", "coordinates": [-58.4, -34.6]}
    collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"comuna": 1, "barrios": "Retiro"},
                "geometry": geometry,
            },
            {"type": "Feature", "properties": {"comuna": 2, "barrios": None}, "geometry": geometry},
        ],
    }
    path = tmp_path / "comunas.geojson"
    path.write_text(json.dumps(collection))
    input_file = inspect_source(Source("comunas", path.name, kind="geojson"), path)

    rows = geojson_rows(input_file)

    assert [c.name for c in input_file.columns] == ["comuna", "barrios", "geometry"]
    assert rows[0][:2] == ["1", "Retiro"]
    assert rows[1][:2] == ["2", None]
    assert json.loads(rows[0][2]) == geometry
