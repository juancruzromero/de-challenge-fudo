import pytest

from provision import (
    DATABASE_NAME,
    MetabaseError,
    ProvisionError,
    Settings,
    ensure_admin,
    ensure_database,
    login,
    remove_sample_content,
    wait_for_sync,
)

ENV = {
    "MB_ADMIN_EMAIL": "admin@example.com",
    "MB_ADMIN_PASSWORD": "secret1",
    "POSTGRES_DB": "ecobici",
    "BI_DB_USER": "bi_reader",
    "BI_DB_PASSWORD": "bi-secret",
}


class FakeMetabase:
    """Responde según (método, path) y registra cada llamada."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []
        self.session_id = None

    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        response = self.responses.get((method, path))
        if isinstance(response, Exception):
            raise response
        return response() if callable(response) else response

    def get(self, path):
        return self.request("GET", path)

    def post(self, path, body=None):
        return self.request("POST", path, body)

    def put(self, path, body):
        return self.request("PUT", path, body)


@pytest.fixture
def settings():
    return Settings.from_env(ENV)


def test_settings_from_env_defaults_and_missing():
    settings = Settings.from_env(ENV)
    assert settings.url == "http://metabase:3000"
    assert settings.db_host == "postgres"
    assert "secret" not in repr(settings)
    with pytest.raises(ProvisionError, match="BI_DB_PASSWORD"):
        Settings.from_env({k: v for k, v in ENV.items() if k != "BI_DB_PASSWORD"})


def test_ensure_admin_runs_setup_only_once(settings):
    fresh = FakeMetabase(
        {("GET", "/api/session/properties"): {"has-user-setup": False, "setup-token": "tok"}}
    )
    assert ensure_admin(fresh, settings) is True
    method, path, body = fresh.calls[-1]
    assert (method, path) == ("POST", "/api/setup")
    assert body["token"] == "tok"
    assert body["user"]["email"] == "admin@example.com"
    assert body["prefs"]["allow_tracking"] is False

    done = FakeMetabase({("GET", "/api/session/properties"): {"has-user-setup": True}})
    assert ensure_admin(done, settings) is False
    assert [c[1] for c in done.calls] == ["/api/session/properties"]


def test_login_sets_session_and_explains_bad_credentials(settings):
    client = FakeMetabase({("POST", "/api/session"): {"id": "abc"}})
    login(client, settings)
    assert client.session_id == "abc"

    bad = FakeMetabase({("POST", "/api/session"): MetabaseError("POST", "/api/session", 401, "")})
    with pytest.raises(ProvisionError, match="make reset"):
        login(bad, settings)


def test_ensure_database_creates_then_updates(settings):
    new = FakeMetabase(
        {
            ("GET", "/api/database"): {"data": [{"id": 1, "name": "Otra"}]},
            ("POST", "/api/database"): {"id": 7},
        }
    )
    assert ensure_database(new, settings) == 7
    body = new.calls[-1][2]
    assert body["details"]["user"] == "bi_reader"
    assert body["details"]["schema-filters-patterns"] == "gold"

    existing = FakeMetabase({("GET", "/api/database"): [{"id": 3, "name": DATABASE_NAME}]})
    assert ensure_database(existing, settings) == 3
    assert existing.calls[-1][:2] == ("PUT", "/api/database/3")


def test_remove_sample_content(settings):
    client = FakeMetabase(
        {
            ("GET", "/api/database"): {
                "data": [{"id": 1, "name": "Sample Database", "is_sample": True}, {"id": 2}]
            },
            ("GET", "/api/collection/root/items?models=collection"): {
                "data": [{"id": 5, "name": "Examples"}, {"id": 6, "name": "Mía"}]
            },
        }
    )
    remove_sample_content(client)
    writes = [c for c in client.calls if c[0] != "GET"]
    assert writes == [
        ("DELETE", "/api/database/1", None),
        ("PUT", "/api/collection/5", {"archived": True}),
    ]


def test_wait_for_sync_polls_until_expected_tables():
    states = iter(
        [
            {"tables": [{"name": "fct_trips", "schema": "gold"}]},
            {
                "tables": [
                    {"name": t, "schema": "gold"}
                    for t in ("fct_trips", "agg_station_od_monthly", "dim_station")
                ]
            },
        ]
    )
    client = FakeMetabase({("GET", "/api/database/2/metadata"): lambda: next(states)})
    sleeps = []
    tables = wait_for_sync(client, 2, timeout_s=60, sleep=sleeps.append)
    assert "agg_station_od_monthly" in tables
    assert len(sleeps) == 1
    assert client.calls[0][:2] == ("POST", "/api/database/2/sync_schema")


def test_wait_for_sync_times_out():
    client = FakeMetabase({("GET", "/api/database/2/metadata"): {"tables": []}})
    with pytest.raises(ProvisionError, match="no sincronizó"):
        wait_for_sync(client, 2, timeout_s=0, sleep=lambda _: None)


def test_settings_rejects_non_http_url():
    with pytest.raises(ProvisionError, match="MB_URL"):
        Settings.from_env({**ENV, "MB_URL": "file:///etc/passwd"})
