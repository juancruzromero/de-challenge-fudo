"""Configuración del ETL, leída de variables de entorno (.env en docker compose).

Se valida todo al arrancar: si falta algo, el error lista todas las variables faltantes juntas.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from psycopg.conninfo import make_conninfo

LOG_FORMATS = ("json", "text")
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


class ConfigError(ValueError):
    """La configuración del entorno es inválida o está incompleta."""


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str = field(repr=False)
    raw_dir: Path
    reference_dir: Path
    log_level: str = "INFO"
    log_format: str = "json"

    @property
    def conninfo(self) -> str:
        """Cadena de conexión para psycopg, como el usuario `etl`."""
        return make_conninfo(
            host=self.db_host,
            port=self.db_port,
            dbname=self.db_name,
            user=self.db_user,
            password=self.db_password,
            application_name="ecobici-etl",
        )

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if environ is None else environ
        required = {
            "db_host": "POSTGRES_HOST",
            "db_name": "POSTGRES_DB",
            "db_user": "ETL_DB_USER",
            "db_password": "ETL_DB_PASSWORD",
            "raw_dir": "DATA_RAW_DIR",
            "reference_dir": "DATA_REFERENCE_DIR",
        }
        missing = [name for name in required.values() if not env.get(name, "").strip()]
        if missing:
            raise ConfigError(f"Faltan variables de entorno: {', '.join(missing)}")

        errors = []
        port = env.get("POSTGRES_PORT", "5432").strip()
        if not port.isdigit() or not 0 < int(port) < 65536:
            errors.append(f"POSTGRES_PORT debe ser un puerto válido, no {port!r}")
        log_level = env.get("LOG_LEVEL", "INFO").strip().upper()
        if log_level not in LOG_LEVELS:
            errors.append(f"LOG_LEVEL debe ser uno de {LOG_LEVELS}, no {log_level!r}")
        log_format = env.get("LOG_FORMAT", "json").strip().lower()
        if log_format not in LOG_FORMATS:
            errors.append(f"LOG_FORMAT debe ser uno de {LOG_FORMATS}, no {log_format!r}")
        if errors:
            raise ConfigError("; ".join(errors))

        values = {attr: env[name].strip() for attr, name in required.items()}
        return cls(
            db_host=values["db_host"],
            db_port=int(port),
            db_name=values["db_name"],
            db_user=values["db_user"],
            db_password=env["ETL_DB_PASSWORD"],  # sin strip: puede tener espacios a propósito
            raw_dir=Path(values["raw_dir"]),
            reference_dir=Path(values["reference_dir"]),
            log_level=log_level,
            log_format=log_format,
        )
