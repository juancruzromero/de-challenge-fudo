import json
import logging

import pytest

from ingest.log import JsonFormatter, TextFormatter, configure_logging, stage


def make_record(**extra) -> logging.LogRecord:
    record = logging.makeLogRecord(
        {"name": "ingest", "levelname": "INFO", "levelno": logging.INFO, "msg": "tabla cargada"}
    )
    record.__dict__.update(extra)
    return record


def test_json_formatter_emits_one_json_object_with_extra_fields():
    line = JsonFormatter().format(make_record(table="trips", rows=3_156_182))

    event = json.loads(line)
    assert event["message"] == "tabla cargada"
    assert event["level"] == "INFO"
    assert event["logger"] == "ingest"
    assert (event["table"], event["rows"]) == ("trips", 3_156_182)
    assert event["ts"].endswith("+00:00")


def test_json_formatter_keeps_non_ascii_text():
    line = JsonFormatter().format(make_record(tipo="AUTOMÁTICA"))

    assert "AUTOMÁTICA" in line


def test_text_formatter_appends_key_value_pairs():
    line = TextFormatter().format(make_record(table="trips", rows=10))

    assert line.endswith("INFO    ingest tabla cargada table=trips rows=10")


def test_configure_logging_replaces_handlers(capsys):
    configure_logging("INFO", "json")
    configure_logging("INFO", "json")
    logging.getLogger("ingest").info("hola", extra={"n": 1})

    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["n"] == 1


def test_stage_logs_start_end_duration_and_result_fields(caplog):
    logger = logging.getLogger("ingest.test")
    with caplog.at_level(logging.INFO), stage(logger, "load_bronze", table="trips") as result:
        result["rows"] = 42

    started, finished = caplog.records
    assert started.message == "etapa iniciada"
    assert (started.stage, started.table) == ("load_bronze", "trips")
    assert finished.message == "etapa terminada"
    assert finished.rows == 42
    assert finished.duration_s >= 0


def test_stage_logs_failure_and_reraises(caplog):
    logger = logging.getLogger("ingest.test")
    with caplog.at_level(logging.INFO), pytest.raises(RuntimeError), stage(logger, "load_bronze"):
        raise RuntimeError("boom")

    failed = caplog.records[-1]
    assert failed.message == "etapa fallida"
    assert failed.levelno == logging.ERROR
    assert failed.exc_info is not None
