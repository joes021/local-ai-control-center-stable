from pathlib import Path

from local_ai_control_center_installer.control_center_panel import (
    run_control_center_panel_entry,
)


def test_panel_entry_starts_runtime_autostart_thread_when_launching_ui(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    captured: dict[str, object] = {}

    class FakeThread:
        def __init__(self, target=None, args=(), kwargs=None, daemon=None):
            captured["target"] = target
            captured["args"] = args
            captured["kwargs"] = kwargs or {}
            captured["daemon"] = daemon

        def start(self):
            captured["started"] = True

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_panel._health_ready",
        lambda url: False,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_panel._port_in_use",
        lambda host, port: False,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_panel.threading.Thread",
        FakeThread,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_panel.uvicorn.run",
        lambda *args, **kwargs: None,
    )

    result = run_control_center_panel_entry(["--install-root", str(install_root)])

    assert result == 0
    assert captured["started"] is True
    assert captured["target"].__name__ == "_ensure_runtime_ready_after_panel_boot"
    assert captured["daemon"] is True
