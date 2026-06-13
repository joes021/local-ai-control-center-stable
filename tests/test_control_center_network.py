import importlib


def test_detect_tailscale_ip_reuses_recent_probe(monkeypatch):
    module = importlib.import_module(
        "local_ai_control_center_installer.control_center_backend.services.network_service"
    )
    module = importlib.reload(module)

    calls: list[dict[str, object]] = []

    class FakeCompletedProcess:
        returncode = 0
        stdout = "100.64.0.55\n"
        stderr = ""

    def fake_run(*args, **kwargs):
        calls.append(kwargs)
        return FakeCompletedProcess()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    first = module.detect_tailscale_ip()
    second = module.detect_tailscale_ip()

    assert first == "100.64.0.55"
    assert second == first
    assert len(calls) == 1
    assert calls[0]["creationflags"] == getattr(module.subprocess, "CREATE_NO_WINDOW", 0)
