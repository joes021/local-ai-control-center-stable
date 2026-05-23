import pytest


@pytest.fixture(autouse=True)
def skip_runtime_launch_probe_by_default(monkeypatch):
    monkeypatch.setenv("LACC_SKIP_RUNTIME_LAUNCH_PROBE", "1")
