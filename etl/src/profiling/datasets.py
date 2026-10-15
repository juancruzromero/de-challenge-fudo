"""Qué se perfila de cada archivo de entrada.

Los nombres de columna son los originales de cada CSV: el profiling corre antes de cualquier
normalización. Los rangos esperados reflejan las reglas de calidad de spec.md (FR-07).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

Row = dict[str, str]

# Caja que contiene a la Ciudad de Buenos Aires, con margen: detecta coordenadas en 0 o invertidas.
LAT_RANGE = (-34.75, -34.50)
LON_RANGE = (-58.55, -58.30)


@dataclass(frozen=True)
class NumericRule:
    column: str
    min_value: float | None = None
    max_value: float | None = None


@dataclass(frozen=True)
class DateRule:
    column: str
    year: int | None = None
    monthly: bool = False


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    title: str
    file: str
    unique: tuple[str, ...] = ()
    numeric: tuple[NumericRule, ...] = ()
    dates: tuple[DateRule, ...] = ()
    categorical: tuple[str, ...] = ()
    # nombre de la clave -> columnas cuyos valores (normalizados) se cuentan para los cruces
    keys: dict[str, tuple[str, ...]] = field(default_factory=dict)
    # nombre del chequeo -> pares (columna id, columna valor) que deberían ser 1 a 1
    consistency: dict[str, tuple[tuple[str, str], ...]] = field(default_factory=dict)
    # nombre del chequeo -> condición por fila; se cuenta cuántas filas la cumplen
    row_checks: dict[str, Callable[[Row], bool]] = field(default_factory=dict)


def _same_station(row: Row) -> bool:
    return row["id_estacion_origen"] == row["id_estacion_destino"]


def _destination_before_origin(row: Row) -> bool:
    origin, destination = row["fecha_origen_recorrido"], row["fecha_destino_recorrido"]
    return bool(origin and destination) and destination < origin


TRIPS = DatasetSpec(
    name="trips",
    title="Viajes 2025",
    file="ecobici-datasets-2025.csv",
    unique=("Id_recorrido",),
    numeric=(
        NumericRule("duracion_recorrido", min_value=1, max_value=86_400),
        NumericRule("lat_estacion_origen", *LAT_RANGE),
        NumericRule("long_estacion_origen", *LON_RANGE),
        NumericRule("lat_estacion_destino", *LAT_RANGE),
        NumericRule("long_estacion_destino", *LON_RANGE),
    ),
    dates=(
        DateRule("fecha_origen_recorrido", year=2025, monthly=True),
        DateRule("fecha_destino_recorrido"),
    ),
    categorical=("modelo_bicicleta", "género"),
    keys={
        "user": ("id_usuario",),
        "station": ("id_estacion_origen", "id_estacion_destino"),
    },
    consistency={
        "IDs de estación con más de un nombre": (
            ("id_estacion_origen", "nombre_estacion_origen"),
            ("id_estacion_destino", "nombre_estacion_destino"),
        ),
    },
    row_checks={
        "misma estación de origen y destino": _same_station,
        "fecha de destino anterior a la de origen": _destination_before_origin,
    },
)

USERS_2025 = DatasetSpec(
    name="users_2025",
    title="Usuarios con alta en 2025",
    file="usuarios-ecobici-2025.csv",
    unique=("ID Cliente",),
    numeric=(NumericRule("edad_usuario", min_value=15, max_value=100),),
    dates=(DateRule("fecha_alta", year=2025, monthly=True),),
    categorical=("genero_usuario", "Customer Has Dni (Yes / No)"),
    keys={"user": ("ID Cliente",)},
)

USERS_2024 = DatasetSpec(
    name="users_2024",
    title="Usuarios con alta en 2024",
    file="usuarios-ecobici-2024.csv",
    unique=("id_usuario",),
    numeric=(NumericRule("edad_usuario", min_value=15, max_value=100),),
    dates=(DateRule("fecha_alta", year=2024, monthly=True),),
    categorical=("genero_usuario",),
    keys={"user": ("id_usuario",)},
)

STATIONS = DatasetSpec(
    name="stations",
    title="Estaciones (sistema actual)",
    file="estaciones.csv",
    unique=("id", "numero_de_estacion"),
    numeric=(NumericRule("latitud", *LAT_RANGE), NumericRule("longitud", *LON_RANGE)),
    keys={"station": ("id",)},
)

STATIONS_LEGACY = DatasetSpec(
    name="stations_legacy",
    title="Estaciones (sistema viejo)",
    file="estaciones-sistema-viejo.csv",
    unique=("id_estacion",),
    numeric=(NumericRule("lat_estacion", *LAT_RANGE), NumericRule("long_estacion", *LON_RANGE)),
    categorical=("tipo_estacion",),
    keys={"station": ("id_estacion",)},
)

DATASETS: tuple[DatasetSpec, ...] = (TRIPS, USERS_2025, USERS_2024, STATIONS, STATIONS_LEGACY)

COMUNAS_FILE = "comunas.geojson"
