"""Definición del dashboard de Metabase (T7.2): preguntas, visualizaciones y grilla.

Todas las preguntas son SQL nativo sobre gold, para que se puedan leer y copiar. Las de la
pestaña de viajes leen agg_station_od_monthly (NFR-07) y aceptan los filtros del dashboard como
field filters; las de Q1–Q6 leen los marts. provision.py las crea o actualiza por API.

Grilla de Metabase: 24 columnas; `size` es (ancho, alto) y `pos` es (fila, columna).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

COLLECTION_NAME = "Ecobici BA 2025"
DASHBOARD_NAME = "Ecobici BA 2025: viajes entre estaciones"
DASHBOARD_DESCRIPTION = (
    "Volumen de viajes entre estaciones a lo largo de 2025 y respuestas a las preguntas del "
    "challenge. Generado por metabase/provision.py: los cambios hechos a mano se pisan en el "
    "próximo make up."
)

OD_TABLE = "agg_station_od_monthly"
TAB_TRIPS = "Viajes entre estaciones"
TAB_QUESTIONS = "Preguntas del challenge"


@dataclass(frozen=True)
class Filter:
    """Filtro del dashboard, conectado a una columna del agregado OD (field filter)."""

    slug: str
    name: str
    column: str


FILTERS = (
    Filter("mes", "Mes", "year_month"),
    Filter("comuna_origen", "Comuna de origen", "origin_comuna_label"),
    Filter("comuna_destino", "Comuna de destino", "destination_comuna_label"),
)

# Condición que va en el WHERE de las preguntas filtrables: un field filter vacío vale `true`.
OD_WHERE = " and ".join("{{" + f.slug + "}}" for f in FILTERS)


@dataclass(frozen=True)
class Card:
    name: str
    sql: str
    display: str
    tab: str
    pos: tuple[int, int]
    size: tuple[int, int]
    description: str = ""
    settings: dict = field(default_factory=dict)
    filtered: bool = False  # recibe los filtros del dashboard


@dataclass(frozen=True)
class Text:
    """Tarjeta de texto (Markdown) del dashboard."""

    text: str
    tab: str
    pos: tuple[int, int]
    size: tuple[int, int]


def tag_id(slug: str) -> str:
    """ID estable del template tag: el mismo en cada provisión, así los cambios no lo rompen."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"ecobici/metabase/{slug}"))


def bar(dimensions: list[str], metrics: list[str], **extra) -> dict:
    return {"graph.dimensions": dimensions, "graph.metrics": metrics, **extra}


# --------------------------------------------------------------------------------------------
# Pestaña 1: viajes entre estaciones (filtrable)
# --------------------------------------------------------------------------------------------

TRIPS_CARDS = (
    Card(
        name="Viajes",
        sql=f"""
select sum(trips) as "Viajes"
from gold.agg_station_od_monthly
where {OD_WHERE}
""",
        display="scalar",
        tab=TAB_TRIPS,
        pos=(3, 0),
        size=(6, 3),
        filtered=True,
    ),
    Card(
        name="Recorridos origen-destino distintos",
        sql=f"""
select count(distinct (origin_station_id, destination_station_id)) as "Recorridos"
from gold.agg_station_od_monthly
where {OD_WHERE}
""",
        display="scalar",
        tab=TAB_TRIPS,
        pos=(3, 6),
        size=(6, 3),
        description="Pares estación de origen → estación de destino con al menos un viaje.",
        filtered=True,
    ),
    Card(
        name="Viajes dentro de la misma comuna (%)",
        sql=f"""
select
    round(
        100.0 * sum(trips) filter (where origin_comuna = destination_comuna)
        / nullif(sum(trips), 0),
        1
    ) as "Misma comuna"
from gold.agg_station_od_monthly
where {OD_WHERE}
""",
        display="scalar",
        tab=TAB_TRIPS,
        pos=(3, 12),
        size=(6, 3),
        filtered=True,
    ),
    Card(
        name="Viajes de ida y vuelta (%)",
        sql=f"""
select
    round(100.0 * sum(trips) filter (where is_round_trip) / nullif(sum(trips), 0), 1)
        as "Ida y vuelta"
from gold.agg_station_od_monthly
where {OD_WHERE}
""",
        display="scalar",
        tab=TAB_TRIPS,
        pos=(3, 18),
        size=(6, 3),
        description="Viajes que terminan en la misma estación en la que empezaron.",
        settings={"scalar.suffix": " %"},
        filtered=True,
    ),
    Card(
        name="Viajes por mes",
        sql=f"""
select
    year_month as "Mes",
    sum(trips) as "Viajes"
from gold.agg_station_od_monthly
where {OD_WHERE}
group by year_month
order by year_month
""",
        display="line",
        tab=TAB_TRIPS,
        pos=(6, 0),
        size=(24, 6),
        settings=bar(["Mes"], ["Viajes"], **{"graph.show_values": True}),
        filtered=True,
    ),
    Card(
        name="Top 20 recorridos entre estaciones",
        sql=f"""
select
    origin_station_name as "Estación de origen",
    origin_comuna_label as "Comuna de origen",
    destination_station_name as "Estación de destino",
    destination_comuna_label as "Comuna de destino",
    sum(trips) as "Viajes",
    round(sum(trips * avg_duration_minutes) / sum(trips), 1) as "Duración media (min)",
    max(distance_m) as "Distancia (m)"
from gold.agg_station_od_monthly
where {OD_WHERE}
group by
    origin_station_name,
    origin_comuna_label,
    destination_station_name,
    destination_comuna_label
order by "Viajes" desc
limit 20
""",
        display="table",
        tab=TAB_TRIPS,
        pos=(12, 0),
        size=(14, 10),
        description="Distancia en línea recta entre las estaciones, no el recorrido real.",
        filtered=True,
    ),
    Card(
        name="Mapa: viajes que salen de cada estación",
        sql=f"""
select
    origin_station_name as "Estación",
    origin_latitude as "Latitud",
    origin_longitude as "Longitud",
    sum(trips) as "Viajes"
from gold.agg_station_od_monthly
where {OD_WHERE} and origin_latitude is not null
group by origin_station_name, origin_latitude, origin_longitude
""",
        display="map",
        tab=TAB_TRIPS,
        pos=(12, 14),
        size=(10, 10),
        settings={
            "map.type": "pin",
            "map.latitude_column": "Latitud",
            "map.longitude_column": "Longitud",
            "map.metric_column": "Viajes",
        },
        filtered=True,
    ),
    Card(
        name="Flujos entre comunas",
        sql=f"""
select
    'Origen: ' || origin_comuna_label as "Comuna de origen",
    'Destino: ' || destination_comuna_label as "Comuna de destino",
    sum(trips) as "Viajes"
from gold.agg_station_od_monthly
where
    {OD_WHERE}
    and origin_comuna_label is not null
    and destination_comuna_label is not null
    and origin_comuna_label <> destination_comuna_label
group by origin_comuna_label, destination_comuna_label
order by "Viajes" desc
limit 40
""",
        display="sankey",
        tab=TAB_TRIPS,
        pos=(22, 0),
        size=(24, 12),
        description=(
            "Los 40 flujos entre comunas distintas con más viajes; los que quedan dentro de "
            "una comuna están en el indicador de arriba. Origen y destino van como nodos "
            "distintos para que un ida y vuelta entre dos comunas no forme un ciclo."
        ),
        settings={
            "sankey.source": "Comuna de origen",
            "sankey.target": "Comuna de destino",
            "sankey.value": "Viajes",
        },
        filtered=True,
    ),
)

# --------------------------------------------------------------------------------------------
# Pestaña 2: preguntas del challenge (marts, sin filtros)
# --------------------------------------------------------------------------------------------

QUESTION_CARDS = (
    Card(
        name="Q1 · Comunas de las que más viajes parten",
        sql="""
select
    coalesce(comuna_label, 'Sin comuna') as "Comuna",
    trips as "Viajes",
    pct_trips as "% de los viajes",
    stations as "Estaciones"
from gold.mart_q1_comunas_origin
order by ranking
""",
        display="row",
        tab=TAB_QUESTIONS,
        pos=(3, 0),
        size=(12, 10),
        settings=bar(
            ["Comuna"],
            ["Viajes"],
            **{"graph.show_values": True, "graph.max_categories_enabled": False},
        ),
    ),
    Card(
        name="Q2 · Comunas que más viajes reciben",
        sql="""
select
    coalesce(comuna_label, 'Sin comuna') as "Comuna",
    trips as "Viajes",
    pct_trips as "% de los viajes",
    stations as "Estaciones"
from gold.mart_q2_comunas_destination
order by ranking
""",
        display="row",
        tab=TAB_QUESTIONS,
        pos=(3, 12),
        size=(12, 10),
        settings=bar(
            ["Comuna"],
            ["Viajes"],
            **{"graph.show_values": True, "graph.max_categories_enabled": False},
        ),
    ),
    Card(
        name="Q3 · Viajes por usuario según rango etario",
        sql="""
select
    age_group as "Rango etario",
    trips_per_user as "Viajes por usuario",
    trips_per_active_user as "Viajes por usuario activo",
    pct_active_users as "% de usuarios activos"
from gold.mart_q3_trips_by_age_group
order by sort_order
""",
        display="bar",
        tab=TAB_QUESTIONS,
        pos=(13, 0),
        size=(15, 8),
        description=(
            "Solo usuarios con perfil (altas 2024 y 2025, ADR 003), incluidos los que no viajaron."
        ),
        settings=bar(["Rango etario"], ["Viajes por usuario", "Viajes por usuario activo"]),
    ),
    Card(
        name="Q3 · Correlación entre edad y viajes",
        sql="""
select
    universe as "Universo",
    pearson_r as "r de Pearson",
    r_squared as "R²"
from gold.mart_q3_age_correlation
""",
        display="table",
        tab=TAB_QUESTIONS,
        pos=(13, 15),
        size=(9, 8),
        description="r cerca de 0: la edad casi no explica cuánto viaja alguien.",
    ),
    Card(
        name="Q4 · Viajes cada 30 días según mes de alta",
        sql="""
select
    signup_year_month as "Mes de alta",
    trips_per_30_days as "Viajes cada 30 días",
    pct_active_users as "% de usuarios activos"
from gold.mart_q4_trips_by_signup_month
order by signup_month
""",
        display="combo",
        tab=TAB_QUESTIONS,
        pos=(21, 0),
        size=(24, 8),
        description=(
            "Normalizado por los días de 2025 en que cada usuario ya estaba dado de alta, para "
            "comparar cohortes con distinta antigüedad."
        ),
        settings=bar(
            ["Mes de alta"],
            ["Viajes cada 30 días", "% de usuarios activos"],
            **{
                "series_settings": {
                    "Viajes cada 30 días": {"display": "bar"},
                    "% de usuarios activos": {"display": "line", "axis": "right"},
                }
            },
        ),
    ),
    Card(
        name="Q5 · Duración por modelo de bicicleta",
        sql="""
select
    bike_model as "Modelo",
    trips as "Viajes",
    median_duration_minutes as "Mediana (min)",
    p25_duration_minutes as "P25 (min)",
    p75_duration_minutes as "P75 (min)",
    p90_duration_minutes as "P90 (min)",
    avg_speed_kmh as "Velocidad media (km/h)"
from gold.mart_q5_duration_by_bike_model
order by bike_model
""",
        display="table",
        tab=TAB_QUESTIONS,
        pos=(29, 0),
        size=(24, 4),
    ),
    Card(
        name="Q5 · Duración mediana por tramo de distancia",
        sql="""
select
    distance_band as "Tramo de distancia",
    bike_model as "Modelo",
    median_duration_minutes as "Mediana (min)"
from gold.mart_q5_duration_by_model_and_distance
where distance_band <> 'Sin distancia'
order by distance_band_order, bike_model
""",
        display="bar",
        tab=TAB_QUESTIONS,
        pos=(33, 0),
        size=(24, 7),
        description=(
            "Misma comparación dentro de cada tramo: aísla el efecto del modelo. Sin los 94 "
            "viajes sin distancia (estación 510, sin ubicación), que duran ~7 h y aplastan "
            "la escala."
        ),
        settings=bar(["Tramo de distancia", "Modelo"], ["Mediana (min)"]),
    ),
    Card(
        name="Q6 · Usuarios más activos de 2025",
        sql="""
select
    ranking as "Puesto",
    user_id as "Usuario",
    trips as "Viajes",
    total_hours as "Horas totales",
    active_days as "Días con viajes",
    trips_per_active_day as "Viajes por día con viajes",
    favorite_origin_station as "Estación favorita",
    case when has_profile then 'sí' else 'no' end as "Tiene perfil",
    age_group as "Rango etario"
from gold.mart_q6_top_users
order by ranking
""",
        display="table",
        tab=TAB_QUESTIONS,
        pos=(40, 0),
        size=(24, 10),
        description="Top 100 por cantidad de viajes. Sin perfil: alta anterior a 2024 (ADR 003).",
    ),
)

CARDS = TRIPS_CARDS + QUESTION_CARDS

TEXTS = (
    Text(
        "## Viajes entre estaciones\n"
        "Volumen de viajes de Ecobici en 2025, entre estaciones y comunas. Los filtros de arriba "
        "aplican a toda esta pestaña. Fuente: `gold.agg_station_od_monthly`.",
        TAB_TRIPS,
        (0, 0),
        (24, 3),
    ),
    Text(
        "## Preguntas del challenge\n"
        "Cada tarjeta lee un mart de gold (`gold.mart_q*`); las mismas consultas, comentadas, "
        "están en `sql/analysis/`. Edad y fecha de alta solo existen para los usuarios dados de "
        "alta en 2024 o 2025: el 49 % de los viajes (ADR 003).",
        TAB_QUESTIONS,
        (0, 0),
        (24, 3),
    ),
)


# --------------------------------------------------------------------------------------------
# Payloads de la API
# --------------------------------------------------------------------------------------------


def template_tags(field_ids: dict[str, int]) -> dict:
    """Template tags de los filtros: field filters sobre las columnas del agregado OD."""
    return {
        f.slug: {
            "id": tag_id(f.slug),
            "name": f.slug,
            "display-name": f.name,
            "type": "dimension",
            "dimension": ["field", field_ids[f.column], None],
            "widget-type": "string/=",
        }
        for f in FILTERS
    }


def card_payload(
    card: Card, database_id: int, collection_id: int, field_ids: dict[str, int]
) -> dict:
    native = {"query": card.sql.strip()}
    if card.filtered:
        native["template-tags"] = template_tags(field_ids)
    return {
        "name": card.name,
        "description": card.description or None,
        "display": card.display,
        "collection_id": collection_id,
        "visualization_settings": card.settings,
        "dataset_query": {"type": "native", "database": database_id, "native": native},
    }


def dashboard_parameters() -> list[dict]:
    return [
        {"id": f.slug, "name": f.name, "slug": f.slug, "type": "string/=", "sectionId": "string"}
        for f in FILTERS
    ]


def dashcards_payload(card_ids: dict[str, int], tab_ids: dict[str, int]) -> list[dict]:
    """Tarjetas del dashboard con su posición. IDs negativos: Metabase las crea de nuevo."""
    dashcards = []
    for index, card in enumerate(CARDS, start=1):
        card_id = card_ids[card.name]
        mappings = [
            {
                "parameter_id": f.slug,
                "card_id": card_id,
                "target": ["dimension", ["template-tag", f.slug]],
            }
            for f in FILTERS
            if card.filtered
        ]
        dashcards.append(
            {
                "id": -index,
                "card_id": card_id,
                "dashboard_tab_id": tab_ids[card.tab],
                "row": card.pos[0],
                "col": card.pos[1],
                "size_x": card.size[0],
                "size_y": card.size[1],
                "parameter_mappings": mappings,
                "visualization_settings": {},
            }
        )
    for index, text in enumerate(TEXTS, start=len(CARDS) + 1):
        dashcards.append(
            {
                "id": -index,
                "card_id": None,
                "dashboard_tab_id": tab_ids[text.tab],
                "row": text.pos[0],
                "col": text.pos[1],
                "size_x": text.size[0],
                "size_y": text.size[1],
                "parameter_mappings": [],
                "visualization_settings": {
                    "virtual_card": {
                        "name": None,
                        "display": "text",
                        "visualization_settings": {},
                        "dataset_query": {},
                        "archived": False,
                    },
                    "text": text.text,
                },
            }
        )
    return dashcards
