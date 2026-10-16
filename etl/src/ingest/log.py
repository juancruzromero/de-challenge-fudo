"""Logging estructurado del ETL.

Cada evento es una línea con campos además del mensaje, para que los conteos por etapa
(leídas, cargadas, rechazadas) se puedan filtrar y comparar (NFR-04):

    log.info("tabla cargada", extra={"table": "trips", "rows": 3156182})

- `json`: una línea JSON por evento; es el formato del contenedor.
- `text`: `hora nivel logger mensaje clave=valor`; para leer en la terminal.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

# Atributos propios de LogRecord: todo lo demás vino en `extra` y se emite como campo.
_RESERVED = set(vars(logging.makeLogRecord({}))) | {"message", "asctime", "taskName"}


def _fields(record: logging.LogRecord) -> dict[str, object]:
    return {key: value for key, value in vars(record).items() if key not in _RESERVED}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **_fields(record),
        }
        if record.exc_info:
            event["exception"] = self.formatException(record.exc_info)
        return json.dumps(event, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        when = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        extras = " ".join(f"{key}={value}" for key, value in _fields(record).items())
        line = f"{when} {record.levelname:<7} {record.name} {record.getMessage()}"
        line = f"{line} {extras}" if extras else line
        if record.exc_info:
            line = f"{line}\n{self.formatException(record.exc_info)}"
        return line


def configure_logging(level: str = "INFO", fmt: str = "json") -> None:
    """Configura el logger raíz: un único handler a stdout. Se puede llamar más de una vez."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if fmt == "json" else TextFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)


@contextmanager
def stage(logger: logging.Logger, name: str, **fields: object) -> Iterator[dict[str, object]]:
    """Loguea inicio, fin y duración de una etapa. Los campos que se agreguen al dict que
    devuelve (por ejemplo, filas cargadas) salen en el evento de fin."""
    result: dict[str, object] = {}
    logger.info("etapa iniciada", extra={"stage": name, **fields})
    started = time.perf_counter()
    try:
        yield result
    except Exception:
        logger.exception(
            "etapa fallida",
            extra={"stage": name, **fields, "duration_s": _elapsed(started)},
        )
        raise
    logger.info(
        "etapa terminada",
        extra={"stage": name, **fields, **result, "duration_s": _elapsed(started)},
    )


def _elapsed(started: float) -> float:
    return round(time.perf_counter() - started, 3)
