import ingest


def test_package_exposes_version():
    assert ingest.__version__ == "0.1.0"
