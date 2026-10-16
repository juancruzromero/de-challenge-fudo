import re

import pytest
from test_provision import FakeMetabase

import dashboard
from provision import ensure_cards, ensure_dashboard

FIELD_IDS = {f.column: index for index, f in enumerate(dashboard.FILTERS, start=10)}


def test_card_names_are_unique():
    names = [card.name for card in dashboard.CARDS]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("tab", [dashboard.TAB_TRIPS, dashboard.TAB_QUESTIONS])
def test_layout_fits_grid_without_overlaps(tab):
    cells = set()
    tiles = [(c.pos, c.size) for c in dashboard.CARDS if c.tab == tab]
    tiles += [(t.pos, t.size) for t in dashboard.TEXTS if t.tab == tab]
    for (row, col), (width, height) in tiles:
        assert col + width <= 24
        tile = {(r, c) for r in range(row, row + height) for c in range(col, col + width)}
        assert not cells & tile, f"superposición en fila {row}, columna {col}"
        cells |= tile


def test_filtered_cards_use_every_filter_and_others_none():
    for card in dashboard.CARDS:
        tags = set(re.findall(r"\{\{(\w+)\}\}", card.sql))
        expected = {f.slug for f in dashboard.FILTERS} if card.filtered else set()
        assert tags == expected, card.name
        if card.filtered:
            assert dashboard.OD_TABLE in card.sql


def test_visualization_settings_reference_sql_columns():
    for card in dashboard.CARDS:
        columns = []
        for key, value in card.settings.items():
            if key in ("graph.dimensions", "graph.metrics"):
                columns += value
            elif key.startswith("sankey.") or (key.startswith("map.") and key.endswith("_column")):
                columns.append(value)
        for column in columns:
            assert f'as "{column}"' in card.sql, f"{card.name}: falta la columna {column}"


def test_card_payload_adds_field_filters_only_when_filtered():
    filtered = next(c for c in dashboard.CARDS if c.filtered)
    payload = dashboard.card_payload(filtered, 1, 2, FIELD_IDS)
    tags = payload["dataset_query"]["native"]["template-tags"]
    assert tags["mes"]["dimension"] == ["field", FIELD_IDS["year_month"], None]
    assert tags["mes"]["id"] == dashboard.tag_id("mes")  # estable entre corridas
    static = next(c for c in dashboard.CARDS if not c.filtered)
    assert (
        "template-tags"
        not in dashboard.card_payload(static, 1, 2, FIELD_IDS)["dataset_query"]["native"]
    )


def test_dashcards_map_filters_and_include_texts():
    card_ids = {card.name: index for index, card in enumerate(dashboard.CARDS, start=100)}
    tab_ids = {dashboard.TAB_TRIPS: -1, dashboard.TAB_QUESTIONS: -2}
    dashcards = dashboard.dashcards_payload(card_ids, tab_ids)
    assert len(dashcards) == len(dashboard.CARDS) + len(dashboard.TEXTS)
    assert len({d["id"] for d in dashcards}) == len(dashcards)
    viajes = next(d for d in dashcards if d["card_id"] == card_ids["Viajes"])
    assert {m["parameter_id"] for m in viajes["parameter_mappings"]} == {
        f.slug for f in dashboard.FILTERS
    }
    texts = [d for d in dashcards if d["card_id"] is None]
    assert all(d["visualization_settings"]["virtual_card"]["display"] == "text" for d in texts)


def test_ensure_cards_creates_updates_and_archives():
    first, second = dashboard.CARDS[0].name, dashboard.CARDS[1].name
    client = FakeMetabase(
        {
            ("GET", "/api/collection/5/items?models=card"): {
                "data": [{"id": 1, "name": first}, {"id": 9, "name": "Vieja"}]
            },
            ("POST", "/api/card"): {"id": 2},
        }
    )
    card_ids = ensure_cards(client, 1, 5, FIELD_IDS)
    assert card_ids[first] == 1
    assert card_ids[second] == 2
    assert ("PUT", "/api/card/1") in [c[:2] for c in client.calls]
    assert ("PUT", "/api/card/9", {"archived": True}) in client.calls


def test_ensure_dashboard_creates_once_and_sets_tabs():
    card_ids = {card.name: index for index, card in enumerate(dashboard.CARDS, start=1)}
    client = FakeMetabase(
        {
            ("GET", "/api/collection/5/items?models=dashboard"): {"data": []},
            ("POST", "/api/dashboard"): {"id": 3},
        }
    )
    assert ensure_dashboard(client, 5, card_ids) == 3
    method, path, body = client.calls[-1]
    assert (method, path) == ("PUT", "/api/dashboard/3")
    assert [t["name"] for t in body["tabs"]] == [dashboard.TAB_TRIPS, dashboard.TAB_QUESTIONS]
    assert [p["slug"] for p in body["parameters"]] == [f.slug for f in dashboard.FILTERS]

    existing = FakeMetabase(
        {
            ("GET", "/api/collection/5/items?models=dashboard"): {
                "data": [{"id": 3, "name": dashboard.DASHBOARD_NAME}]
            }
        }
    )
    ensure_dashboard(existing, 5, card_ids)
    assert ("POST", "/api/dashboard") not in [c[:2] for c in existing.calls]
