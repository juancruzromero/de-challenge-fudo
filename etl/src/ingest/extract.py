"""Archivos de entrada: qué archivo va a qué tabla bronze y cómo leerlo.

No transforma valores: solo detecta el formato (BOM, delimitador), calcula el hash para la
idempotencia (FR-03) y normaliza los nombres de columna a snake_case ASCII (FR-01b).
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

log = logging.getLogger(__name__)

BOM = b"\xef\xbb\xbf"
SNIFF_BYTES = 64 * 1024
HASH_CHUNK_BYTES = 1024 * 1024
IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")

Kind = Literal["csv", "geojson"]
Location = Literal["raw", "reference"]


@dataclass(frozen=True)
class Source:
    """Un archivo esperado y la tabla bronze donde se carga."""

    table: str
    file: str
    kind: Kind = "csv"
    location: Location = "raw"


# Orden de carga: primero las referencias chicas, al final los viajes.
SOURCES: tuple[Source, ...] = (
    Source("comunas", "comunas.geojson", kind="geojson", location="reference"),
    Source("stations", "estaciones.csv"),
    Source("stations_legacy", "estaciones-sistema-viejo.csv"),
    Source("users_2024", "usuarios-ecobici-2024.csv"),
    Source("users_2025", "usuarios-ecobici-2025.csv"),
    Source("trips", "ecobici-datasets-2025.csv"),
)

# Archivos de data/raw/ que se sabe que no se cargan (spec.md §2).
IGNORED_FILES = frozenset({".gitkeep", "ecobici-datasets-2025.zip"})


@dataclass(frozen=True)
class Column:
    original: str
    name: str


@dataclass(frozen=True)
class InputFile:
    source: Source
    path: Path
    sha256: str
    size_bytes: int
    has_bom: bool
    delimiter: str | None
    columns: tuple[Column, ...]

    @property
    def table(self) -> str:
        return self.source.table


class InputError(ValueError):
    """Faltan archivos de entrada o su formato no es el esperado."""


# --------------------------------------------------------------------------------------------
# Nombres de columna
# --------------------------------------------------------------------------------------------


def normalize_column(name: str) -> str:
    """`ID Cliente` -> `id_cliente`, `género` -> `genero`, `Customer Has Dni (Yes / No)` ->
    `customer_has_dni_yes_no`. Si empieza con un número, se le antepone `c_`."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    normalized = re.sub(r"[^a-z0-9]+", "_", ascii_name.lower()).strip("_")
    if not normalized:
        raise InputError(f"La columna {name!r} queda vacía al normalizarla")
    return f"c_{normalized}" if normalized[0].isdigit() else normalized


def normalize_header(header: list[str]) -> tuple[Column, ...]:
    columns = tuple(Column(original, normalize_column(original)) for original in header)
    seen: dict[str, str] = {}
    for column in columns:
        if column.name in seen:
            raise InputError(
                f"Las columnas {seen[column.name]!r} y {column.original!r} "
                f"quedan con el mismo nombre: {column.name!r}"
            )
        seen[column.name] = column.original
    return columns


def validate_identifier(name: str) -> str:
    """Los nombres de tabla y columna se interpolan en SQL: solo se aceptan identificadores
    simples en minúscula (los produce `normalize_column` o vienen de `SOURCES`)."""
    if not IDENTIFIER.fullmatch(name):
        raise InputError(f"Identificador inválido: {name!r}")
    return name


# --------------------------------------------------------------------------------------------
# Archivos
# --------------------------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_csv(path: Path) -> tuple[bool, str, list[str]]:
    """Devuelve (tiene BOM, delimitador, header original)."""
    with path.open("rb") as file:
        head = file.read(SNIFF_BYTES)
    if not head.strip():
        raise InputError(f"{path.name}: el archivo está vacío")
    has_bom = head.startswith(BOM)
    # Solo para detectar el formato: el corte del bloque puede partir un carácter multibyte.
    lines = head.decode("utf-8-sig", errors="ignore").splitlines()
    try:
        delimiter = csv.Sniffer().sniff("\n".join(lines[:20]), delimiters=",;|\t").delimiter
    except csv.Error as error:
        raise InputError(f"{path.name}: no se pudo detectar el delimitador") from error
    header = next(csv.reader([lines[0]], delimiter=delimiter))
    return has_bom, delimiter, header


def geojson_header(path: Path) -> list[str]:
    """Columnas de un FeatureCollection: las `properties` (iguales en todos los features) más
    `geometry`, que se guarda como GeoJSON en texto."""
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    features = data.get("features") if data.get("type") == "FeatureCollection" else None
    if not features:
        raise InputError(f"{path.name}: no es un FeatureCollection con features")
    keys = list(features[0].get("properties") or {})
    for index, feature in enumerate(features):
        if list(feature.get("properties") or {}) != keys:
            raise InputError(f"{path.name}: el feature {index} tiene otras propiedades")
    return [*keys, "geometry"]


def inspect_source(source: Source, path: Path) -> InputFile:
    if source.kind == "csv":
        has_bom, delimiter, header = inspect_csv(path)
    else:
        has_bom, delimiter = path.read_bytes()[:3] == BOM, None
        header = geojson_header(path)
    columns = normalize_header(header)
    validate_identifier(source.table)
    for column in columns:
        validate_identifier(column.name)
    return InputFile(
        source=source,
        path=path,
        sha256=sha256_file(path),
        size_bytes=path.stat().st_size,
        has_bom=has_bom,
        delimiter=delimiter,
        columns=columns,
    )


def discover(
    raw_dir: Path, reference_dir: Path, sources: tuple[Source, ...] = SOURCES
) -> list[InputFile]:
    """Ubica e inspecciona todos los archivos esperados. Si falta alguno, falla listándolos
    todos antes de cargar nada."""
    base = {"raw": raw_dir, "reference": reference_dir}
    paths = [base[source.location] / source.file for source in sources]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise InputError(f"Faltan archivos de entrada (ver README): {', '.join(missing)}")

    expected = {source.file for source in sources if source.location == "raw"}
    unexpected = sorted(
        path.name
        for path in raw_dir.iterdir()
        if path.is_file() and path.name not in expected | IGNORED_FILES
    )
    if unexpected:
        log.warning("archivos de data/raw sin tabla asignada", extra={"files": unexpected})

    inputs = []
    for source, path in zip(sources, paths, strict=True):
        input_file = inspect_source(source, path)
        log.info(
            "archivo de entrada detectado",
            extra={
                "table": input_file.table,
                "file": path.name,
                "size_bytes": input_file.size_bytes,
                "has_bom": input_file.has_bom,
                "delimiter": input_file.delimiter,
                "columns": len(input_file.columns),
                "renamed": {c.original: c.name for c in input_file.columns if c.original != c.name},
                "sha256": input_file.sha256,
            },
        )
        inputs.append(input_file)
    return inputs
