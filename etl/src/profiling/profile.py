"""Profiling de los datasets de entrada.

Recorre cada archivo de data/raw/ sin cargarlo a la base y genera un reporte en Markdown con
formato, columnas, vacíos, duplicados, rangos, valores categóricos y cruces de claves entre
datasets. Es la base de las reglas de limpieza de spec.md.

Uso (desde la raíz del repo):
    uv run --project etl ecobici-profile
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from profiling.datasets import COMUNAS_FILE, DATASETS, DatasetSpec

log = logging.getLogger("profiling")

BOM = b"\xef\xbb\xbf"
SNIFF_BYTES = 64 * 1024
DISTINCT_CAP = 1_000
TOP_VALUES = 10
SAME_LOCATION_METERS = 200


# --------------------------------------------------------------------------------------------
# Normalización mínima para poder cruzar claves (la normalización real vive en silver)
# --------------------------------------------------------------------------------------------


def normalize_id(value: str) -> str:
    """`146BAEcobici` -> `146`, `1.0` -> `1`, `' 7 '` -> `7`."""
    value = value.strip().removesuffix("BAEcobici")
    return value.removesuffix(".0")


def parse_number(value: str) -> tuple[float | None, bool]:
    """Devuelve (número, tenía separador de miles). `"3,108"` -> (3108.0, True)."""
    has_separator = "," in value
    try:
        return float(value.replace(",", "")), has_separator
    except ValueError:
        return None, has_separator


def parse_date(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


# --------------------------------------------------------------------------------------------
# Estadísticas
# --------------------------------------------------------------------------------------------


@dataclass
class FileFormat:
    size_bytes: int
    has_bom: bool
    delimiter: str
    header: list[str]


@dataclass
class ColumnStats:
    empty: int = 0
    distinct: set[str] = field(default_factory=set)
    distinct_overflow: bool = False
    sample: str = ""

    def add(self, value: str) -> None:
        if not value.strip():
            self.empty += 1
            return
        if not self.sample:
            self.sample = value
        if not self.distinct_overflow:
            self.distinct.add(value)
            if len(self.distinct) > DISTINCT_CAP:
                self.distinct_overflow = True
                self.distinct.clear()

    @property
    def distinct_label(self) -> str:
        return (
            f"> {DISTINCT_CAP:,}".replace(",", ".")
            if self.distinct_overflow
            else str(len(self.distinct))
        )


@dataclass
class NumericStats:
    min_value: float | None = None
    max_value: float | None = None
    with_separator: int = 0
    unparseable: Counter[str] = field(default_factory=Counter)
    below: int = 0
    above: int = 0

    def add(self, value: str, min_allowed: float | None, max_allowed: float | None) -> None:
        if not value.strip():
            return
        number, has_separator = parse_number(value)
        self.with_separator += has_separator
        if number is None:
            self.unparseable[value] += 1
            return
        self.min_value = number if self.min_value is None else min(self.min_value, number)
        self.max_value = number if self.max_value is None else max(self.max_value, number)
        self.below += min_allowed is not None and number < min_allowed
        self.above += max_allowed is not None and number > max_allowed


@dataclass
class DateStats:
    min_value: datetime | None = None
    max_value: datetime | None = None
    unparseable: int = 0
    out_of_year: int = 0
    by_month: Counter[str] = field(default_factory=Counter)

    def add(self, value: str, year: int | None) -> None:
        if not value.strip():
            return
        parsed = parse_date(value)
        if parsed is None:
            self.unparseable += 1
            return
        self.min_value = parsed if self.min_value is None else min(self.min_value, parsed)
        self.max_value = parsed if self.max_value is None else max(self.max_value, parsed)
        self.out_of_year += year is not None and parsed.year != year
        self.by_month[parsed.strftime("%Y-%m")] += 1


@dataclass
class DatasetProfile:
    spec: DatasetSpec
    file_format: FileFormat
    rows: int = 0
    columns: dict[str, ColumnStats] = field(default_factory=dict)
    numeric: dict[str, NumericStats] = field(default_factory=dict)
    dates: dict[str, DateStats] = field(default_factory=dict)
    categorical: dict[str, Counter[str]] = field(default_factory=dict)
    duplicates: dict[str, int] = field(default_factory=dict)
    keys: dict[str, Counter[str]] = field(default_factory=dict)
    inconsistent: dict[str, list[str]] = field(default_factory=dict)
    row_checks: Counter[str] = field(default_factory=Counter)
    seconds: float = 0.0


# --------------------------------------------------------------------------------------------
# Lectura
# --------------------------------------------------------------------------------------------


def detect_format(path: Path) -> FileFormat:
    with path.open("rb") as file:
        head = file.read(SNIFF_BYTES)
    has_bom = head.startswith(BOM)
    # Solo para detectar el formato: el cierre del bloque puede cortar un carácter multibyte.
    lines = head.decode("utf-8-sig", errors="ignore").splitlines()
    dialect = csv.Sniffer().sniff("\n".join(lines[:20]), delimiters=",;|\t")
    header = next(csv.reader([lines[0]], delimiter=dialect.delimiter))
    return FileFormat(path.stat().st_size, has_bom, dialect.delimiter, header)


def profile_dataset(path: Path, spec: DatasetSpec) -> DatasetProfile:
    started = time.perf_counter()
    file_format = detect_format(path)
    _check_columns(spec, file_format.header)

    profile = DatasetProfile(spec, file_format)
    profile.columns = {column: ColumnStats() for column in file_format.header}
    profile.numeric = {rule.column: NumericStats() for rule in spec.numeric}
    profile.dates = {rule.column: DateStats() for rule in spec.dates}
    profile.categorical = {column: Counter() for column in spec.categorical}
    profile.keys = {name: Counter() for name in spec.keys}
    seen: dict[str, set[str]] = {column: set() for column in spec.unique}
    duplicates: Counter[str] = Counter()
    values_by_id: dict[str, defaultdict[str, set[str]]] = {
        name: defaultdict(set) for name in spec.consistency
    }

    # utf-8-sig quita el BOM si está y falla con un error claro si el archivo no es UTF-8.
    with path.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file, delimiter=file_format.delimiter):
            profile.rows += 1
            for column, stats in profile.columns.items():
                stats.add(row[column] or "")
            for rule in spec.numeric:
                profile.numeric[rule.column].add(row[rule.column], rule.min_value, rule.max_value)
            for rule in spec.dates:
                profile.dates[rule.column].add(row[rule.column], rule.year)
            for column in spec.categorical:
                profile.categorical[column][row[column].strip()] += 1
            for column, values in seen.items():
                value = row[column].strip()
                if not value:
                    continue  # los vacíos ya se cuentan en ColumnStats
                if value in values:
                    duplicates[column] += 1
                else:
                    values.add(value)
            for name, columns in spec.keys.items():
                for column in columns:
                    if row[column].strip():
                        profile.keys[name][normalize_id(row[column])] += 1
            for name, pairs in spec.consistency.items():
                for id_column, value_column in pairs:
                    if row[id_column].strip() and row[value_column].strip():
                        values_by_id[name][normalize_id(row[id_column])].add(
                            row[value_column].strip()
                        )
            for name, check in spec.row_checks.items():
                profile.row_checks[name] += check(row)

    profile.duplicates = {column: duplicates[column] for column in spec.unique}
    profile.inconsistent = {
        name: sorted((k for k, v in by_id.items() if len(v) > 1), key=_numeric_sort_key)
        for name, by_id in values_by_id.items()
    }
    profile.seconds = time.perf_counter() - started
    return profile


def _check_columns(spec: DatasetSpec, header: list[str]) -> None:
    expected = (
        set(spec.unique)
        | {rule.column for rule in spec.numeric}
        | {rule.column for rule in spec.dates}
        | set(spec.categorical)
        | {column for columns in spec.keys.values() for column in columns}
        | {column for pairs in spec.consistency.values() for pair in pairs for column in pair}
    )
    missing = sorted(expected - set(header))
    if missing:
        raise ValueError(f"{spec.file}: faltan columnas {missing}; header = {header}")


def _numeric_sort_key(value: str) -> tuple[int, str]:
    return (int(value), "") if value.isdigit() else (sys.maxsize, value)


# --------------------------------------------------------------------------------------------
# Cruces entre datasets
# --------------------------------------------------------------------------------------------


@dataclass
class Coverage:
    label: str
    matched_keys: int
    total_keys: int
    matched_weight: int
    total_weight: int
    missing: list[tuple[str, int]]


def coverage(label: str, counts: Counter[str], reference: set[str]) -> Coverage:
    matched = [key for key in counts if key in reference]
    missing = sorted(
        ((key, n) for key, n in counts.items() if key not in reference), key=lambda kv: -kv[1]
    )
    return Coverage(
        label=label,
        matched_keys=len(matched),
        total_keys=len(counts),
        matched_weight=sum(counts[key] for key in matched),
        total_weight=sum(counts.values()),
        missing=missing,
    )


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_m = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi, d_lambda = phi2 - phi1, math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * earth_radius_m * math.asin(math.sqrt(a))


def _in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    previous = ring[-1]
    for current in ring:
        (x1, y1), (x2, y2) = current[:2], previous[:2]
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            inside = not inside
        previous = current
    return inside


def point_in_geometry(lon: float, lat: float, geometry: dict) -> bool:
    """Punto en Polygon/MultiPolygon GeoJSON, respetando huecos (ray casting)."""
    polygons = (
        geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    )
    return any(
        _in_ring(lon, lat, rings[0]) and not any(_in_ring(lon, lat, hole) for hole in rings[1:])
        for rings in polygons
    )


def load_points(path: Path, id_column: str, lat_column: str, lon_column: str) -> dict:
    points: dict[str, tuple[str, float, float]] = {}
    with path.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            lat, _ = parse_number(row[lat_column])
            lon, _ = parse_number(row[lon_column])
            if row[id_column].strip() and lat is not None and lon is not None:
                name = row.get("nombre") or row.get("nombre_estacion") or ""
                points[normalize_id(row[id_column])] = (name, lat, lon)
    return points


@dataclass
class CrossChecks:
    stations: list[Coverage]
    users: list[Coverage]
    trips_per_user: dict[str, float]
    legacy_shared: int
    legacy_same_location: int
    legacy_moved: list[tuple[str, str, str, int]]
    comunas: int
    stations_in_comuna: int
    stations_outside: list[tuple[str, str]]


def cross_checks(profiles: dict[str, DatasetProfile], raw_dir: Path, ref_dir: Path) -> CrossChecks:
    trips = profiles["trips"]
    station_ids = set(profiles["stations"].keys["station"])
    legacy_ids = set(profiles["stations_legacy"].keys["station"])
    users_2025 = set(profiles["users_2025"].keys["user"])
    users_2024 = set(profiles["users_2024"].keys["user"])

    stations = [
        coverage("Catálogo actual (`estaciones.id`)", trips.keys["station"], station_ids),
        coverage("Catálogo viejo (`id_estacion`)", trips.keys["station"], legacy_ids),
    ]
    users = [
        coverage("Altas 2025", trips.keys["user"], users_2025),
        coverage("Altas 2024", trips.keys["user"], users_2024),
        coverage("Altas 2024 + 2025", trips.keys["user"], users_2024 | users_2025),
    ]
    trips_per_user = {
        item.label: item.matched_weight / item.matched_keys if item.matched_keys else 0.0
        for item in users
    }

    current = load_points(raw_dir / "estaciones.csv", "id", "latitud", "longitud")
    legacy = load_points(
        raw_dir / "estaciones-sistema-viejo.csv", "id_estacion", "lat_estacion", "long_estacion"
    )
    shared = sorted(current.keys() & legacy.keys(), key=_numeric_sort_key)
    moved = []
    for station_id in shared:
        old_name, old_lat, old_lon = legacy[station_id]
        new_name, new_lat, new_lon = current[station_id]
        distance = haversine_m(old_lat, old_lon, new_lat, new_lon)
        if distance >= SAME_LOCATION_METERS:
            moved.append((station_id, old_name, new_name, round(distance)))
    moved.sort(key=lambda item: -item[3])

    features = json.loads((ref_dir / COMUNAS_FILE).read_text(encoding="utf-8"))["features"]
    outside = [
        (station_id, name)
        for station_id, (name, lat, lon) in sorted(
            current.items(), key=lambda kv: _numeric_sort_key(kv[0])
        )
        if not any(point_in_geometry(lon, lat, feature["geometry"]) for feature in features)
    ]

    return CrossChecks(
        stations=stations,
        users=users,
        trips_per_user=trips_per_user,
        legacy_shared=len(shared),
        legacy_same_location=len(shared) - len(moved),
        legacy_moved=moved,
        comunas=len(features),
        stations_in_comuna=len(current) - len(outside),
        stations_outside=outside,
    )


# --------------------------------------------------------------------------------------------
# Reporte en Markdown
# --------------------------------------------------------------------------------------------


def fmt_int(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".")


def fmt_num(value: float | None) -> str:
    if value is None:
        return "—"
    return fmt_int(value) if float(value).is_integer() else f"{value:.6f}".rstrip("0")


def fmt_pct(part: float, total: float) -> str:
    return "—" if not total else f"{part / total:.1%}".replace(".", ",").replace("%", " %")


def fmt_share(part: float, total: float) -> str:
    return f"{fmt_int(part)} ({fmt_pct(part, total)})"


def _cell(value: object) -> str:
    text = str(value)
    text = text if len(text) <= 40 else text[:37] + "..."
    return text.replace("|", "\\|").replace("\n", " ")


def md_table(headers: list[str], rows: list[list[object]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]
    return "\n".join(lines)


def render_dataset(profile: DatasetProfile) -> str:
    spec, fmt = profile.spec, profile.file_format
    out = [f"## {spec.title} — `{spec.file}`", ""]
    out.append(
        md_table(
            ["Filas", "Columnas", "Tamaño", "Encoding", "Delimitador", "Tiempo"],
            [
                [
                    fmt_int(profile.rows),
                    len(fmt.header),
                    f"{fmt.size_bytes / 1_000_000:.1f} MB".replace(".", ","),
                    "UTF-8 con BOM" if fmt.has_bom else "UTF-8 sin BOM",
                    f"`{fmt.delimiter}`",
                    f"{profile.seconds:.1f} s".replace(".", ","),
                ]
            ],
        )
    )

    out += ["", "### Columnas", ""]
    out.append(
        md_table(
            ["Columna", "Vacíos", "Distintos", "Ejemplo"],
            [
                [f"`{name}`", fmt_int(stats.empty), stats.distinct_label, stats.sample]
                for name, stats in profile.columns.items()
            ],
        )
    )

    if profile.duplicates:
        out += ["", "### Duplicados", ""]
        out.append(
            md_table(
                ["Columna", "Valores repetidos"],
                [[f"`{column}`", fmt_int(n)] for column, n in profile.duplicates.items()],
            )
        )

    if spec.numeric:
        out += ["", "### Numéricas", ""]
        rows = []
        for rule in spec.numeric:
            stats = profile.numeric[rule.column]
            expected = (
                f"[{fmt_num(rule.min_value)}, {fmt_num(rule.max_value)}]"
                if rule.min_value is not None or rule.max_value is not None
                else "—"
            )
            rows.append(
                [
                    f"`{rule.column}`",
                    fmt_num(stats.min_value),
                    fmt_num(stats.max_value),
                    fmt_int(stats.with_separator),
                    fmt_int(sum(stats.unparseable.values())),
                    expected,
                    fmt_int(stats.below),
                    fmt_int(stats.above),
                ]
            )
        out.append(
            md_table(
                [
                    "Columna",
                    "Mín",
                    "Máx",
                    "Con separador de miles",
                    "No numéricos",
                    "Rango esperado",
                    "Debajo",
                    "Encima",
                ],
                rows,
            )
        )

    if spec.dates:
        out += ["", "### Fechas", ""]
        out.append(
            md_table(
                ["Columna", "Mín", "Máx", "No parseables", "Año esperado", "Fuera del año"],
                [
                    [
                        f"`{rule.column}`",
                        profile.dates[rule.column].min_value,
                        profile.dates[rule.column].max_value,
                        fmt_int(profile.dates[rule.column].unparseable),
                        rule.year or "—",
                        fmt_int(profile.dates[rule.column].out_of_year),
                    ]
                    for rule in spec.dates
                ],
            )
        )
        for rule in spec.dates:
            if rule.monthly:
                by_month = profile.dates[rule.column].by_month
                out += ["", f"Registros por mes (`{rule.column}`):", ""]
                out.append(
                    md_table(
                        ["Mes", "Registros"],
                        [[month, fmt_int(n)] for month, n in sorted(by_month.items())],
                    )
                )

    if spec.categorical:
        out += ["", "### Categóricas", ""]
        for column in spec.categorical:
            counts = profile.categorical[column]
            out += [f"`{column}`:", ""]
            out.append(
                md_table(
                    ["Valor", "Filas", "%"],
                    [
                        [value or "(vacío)", fmt_int(n), fmt_pct(n, profile.rows)]
                        for value, n in counts.most_common(TOP_VALUES)
                    ],
                )
            )
            out.append("")

    checks = [[name, fmt_int(n)] for name, n in profile.row_checks.items()]
    checks += [
        [name, f"{len(ids)} ({', '.join(ids[:10])})" if ids else "0"]
        for name, ids in profile.inconsistent.items()
    ]
    if checks:
        out += ["", "### Chequeos", ""]
        out.append(md_table(["Chequeo", "Casos"], checks))

    return "\n".join(out).rstrip() + "\n"


def render_cross_checks(cross: CrossChecks) -> str:
    out = ["## Cruces entre datasets", "", "### Viajes ↔ estaciones", ""]
    out.append(
        md_table(
            ["Catálogo", "Estaciones de los viajes", "Salidas y llegadas cubiertas", "Faltantes"],
            [
                [
                    item.label,
                    f"{fmt_int(item.matched_keys)} / {fmt_int(item.total_keys)}",
                    fmt_share(item.matched_weight, item.total_weight),
                    ", ".join(f"{key} ({fmt_int(n)})" for key, n in item.missing[:8])
                    + (" …" if len(item.missing) > 8 else ""),
                ]
                for item in cross.stations
            ],
        )
    )

    out += ["", "### Viajes ↔ usuarios", ""]
    out.append(
        md_table(
            ["Archivo de usuarios", "Usuarios con viajes", "Viajes cubiertos", "Viajes/usuario"],
            [
                [
                    item.label,
                    f"{fmt_int(item.matched_keys)} / {fmt_int(item.total_keys)}",
                    fmt_share(item.matched_weight, item.total_weight),
                    f"{cross.trips_per_user[item.label]:.1f}".replace(".", ","),
                ]
                for item in cross.users
            ],
        )
    )

    out += [
        "",
        "### Catálogo viejo ↔ catálogo actual",
        "",
        f"IDs compartidos: **{cross.legacy_shared}**. En la misma ubicación "
        f"(< {SAME_LOCATION_METERS} m): **{cross.legacy_same_location}**. "
        f"En otra ubicación: **{len(cross.legacy_moved)}**.",
        "",
    ]
    out.append(
        md_table(
            ["ID", "Nombre en el viejo", "Nombre en el actual", "Distancia (m)"],
            [[i, old, new, fmt_int(d)] for i, old, new, d in cross.legacy_moved[:10]],
        )
    )

    out += [
        "",
        "### Estaciones ↔ comunas",
        "",
        f"Polígonos: **{cross.comunas}**. Estaciones del catálogo actual dentro de una comuna: "
        f"**{cross.stations_in_comuna}**. Fuera de todas: **{len(cross.stations_outside)}** "
        + (
            "(" + ", ".join(f"{name} ({i})" for i, name in cross.stations_outside) + ")."
            if cross.stations_outside
            else "."
        ),
    ]
    return "\n".join(out) + "\n"


def render_report(profiles: dict[str, DatasetProfile], cross: CrossChecks) -> str:
    header = [
        "# Profiling de datasets",
        "",
        "> Generado por `uv run --project etl ecobici-profile`. No editar a mano: "
        "volver a correr el script.",
        "",
        md_table(
            ["Dataset", "Archivo", "Filas"],
            [[p.spec.title, f"`{p.spec.file}`", fmt_int(p.rows)] for p in profiles.values()],
        ),
        "",
    ]
    body = [render_dataset(profile) for profile in profiles.values()]
    return "\n".join(header) + "\n" + "\n".join(body) + "\n" + render_cross_checks(cross)


# --------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--reference-dir", type=Path, default=Path("data/reference"))
    parser.add_argument("--output", type=Path, default=Path("docs/profiling/profile.md"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    missing = [spec.file for spec in DATASETS if not (args.raw_dir / spec.file).exists()]
    if not (args.reference_dir / COMUNAS_FILE).exists():
        missing.append(str(args.reference_dir / COMUNAS_FILE))
    if missing:
        log.error("Faltan archivos en %s: %s (ver README)", args.raw_dir, missing)
        return 1

    profiles = {}
    for spec in DATASETS:
        log.info("Perfilando %s", spec.file)
        profile = profile_dataset(args.raw_dir / spec.file, spec)
        profiles[spec.name] = profile
        log.info("  %s filas en %.1f s", fmt_int(profile.rows), profile.seconds)

    cross = cross_checks(profiles, args.raw_dir, args.reference_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_report(profiles, cross), encoding="utf-8")
    log.info("Reporte escrito en %s", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
