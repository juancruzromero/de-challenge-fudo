from pathlib import Path

import pytest

from ingest.config import ConfigError, Settings

ENV = {
    "POSTGRES_HOST": "postgres",
    "POSTGRES_PORT": "5432",
    "POSTGRES_DB": "ecobici",
    "ETL_DB_USER": "etl",
    "ETL_DB_PASSWORD": "s3cr3t",
    "DATA_RAW_DIR": "/data/raw",
    "DATA_REFERENCE_DIR": "/data/reference",
}


def test_from_env_reads_all_settings():
    settings = Settings.from_env({**ENV, "LOG_LEVEL": "debug", "LOG_FORMAT": "TEXT"})

    assert settings.db_host == "postgres"
    assert settings.db_port == 5432
    assert settings.raw_dir == Path("/data/raw")
    assert (settings.log_level, settings.log_format) == ("DEBUG", "text")


def test_from_env_uses_defaults_for_optional_settings():
    env = {key: value for key, value in ENV.items() if key != "POSTGRES_PORT"}

    settings = Settings.from_env(env)

    assert (settings.db_port, settings.log_level, settings.log_format) == (5432, "INFO", "json")


def test_from_env_lists_every_missing_variable():
    env = {key: value for key, value in ENV.items() if key not in ("ETL_DB_USER", "DATA_RAW_DIR")}

    with pytest.raises(ConfigError, match="ETL_DB_USER, DATA_RAW_DIR"):
        Settings.from_env(env)


def test_blank_values_count_as_missing():
    with pytest.raises(ConfigError, match="POSTGRES_HOST"):
        Settings.from_env({**ENV, "POSTGRES_HOST": "  "})


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("POSTGRES_PORT", "abc", "POSTGRES_PORT"),
        ("POSTGRES_PORT", "70000", "POSTGRES_PORT"),
        ("LOG_LEVEL", "verbose", "LOG_LEVEL"),
        ("LOG_FORMAT", "xml", "LOG_FORMAT"),
    ],
)
def test_from_env_rejects_invalid_values(key, value, message):
    with pytest.raises(ConfigError, match=message):
        Settings.from_env({**ENV, key: value})


def test_password_is_hidden_from_repr():
    assert "s3cr3t" not in repr(Settings.from_env(ENV))


def test_conninfo_targets_the_etl_user():
    conninfo = Settings.from_env(ENV).conninfo

    assert "host=postgres" in conninfo
    assert "user=etl" in conninfo
    assert "dbname=ecobici" in conninfo
    assert "application_name=ecobici-etl" in conninfo
