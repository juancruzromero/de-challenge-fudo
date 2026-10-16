"""Comando de ingesta: ubica los archivos de entrada y los carga a bronze.

Uso:
    ecobici-ingest            # carga lo que cambió desde la última corrida
    ecobici-ingest --force    # recarga todo
    ecobici-ingest --only trips --only stations
"""

from __future__ import annotations

import argparse
import logging

import psycopg

from ingest.config import ConfigError, Settings
from ingest.extract import SOURCES, InputError, discover
from ingest.load_bronze import load_all
from ingest.log import configure_logging, stage

log = logging.getLogger("ingest")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Carga los archivos de entrada a bronze.")
    parser.add_argument("--force", action="store_true", help="recarga aunque no haya cambios")
    parser.add_argument(
        "--only",
        action="append",
        choices=[source.table for source in SOURCES],
        help="carga solo esta tabla (se puede repetir)",
    )
    args = parser.parse_args(argv)

    try:
        settings = Settings.from_env()
    except ConfigError as error:
        configure_logging("INFO", "text")
        log.error("configuración inválida", extra={"error": str(error)})
        return 2
    configure_logging(settings.log_level, settings.log_format)

    sources = tuple(s for s in SOURCES if not args.only or s.table in args.only)
    try:
        with stage(log, "ingest", tables=[s.table for s in sources]) as summary:
            inputs = discover(settings.raw_dir, settings.reference_dir, sources)
            results = load_all(settings.conninfo, inputs, force=args.force)
            summary["loaded"] = {r.table: r.rows for r in results if r.mode != "skipped"}
            summary["skipped"] = [r.table for r in results if r.mode == "skipped"]
    except (InputError, psycopg.Error):
        return 1  # stage() ya registró el error con su traceback
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
