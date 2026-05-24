from pathlib import Path

import pytest

from local_ai_control_center_installer import control_center_panel as panel_module
from local_ai_control_center_installer.control_center_panel import (
    _module_main,
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


def test_panel_entry_rejects_foreign_panel_on_same_port(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"status":"ok","app":"local-ai-control-center-stable","installRoot":"C:\\\\Other"}'

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_panel.urlopen",
        lambda *args, **kwargs: FakeResponse(),
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_panel._port_in_use",
        lambda host, port: True,
    )

    with pytest.raises(RuntimeError, match="UI port 3210 je vec zauzet drugim procesom."):
        run_control_center_panel_entry(["--install-root", str(install_root)])


def test_panel_module_main_delegates_to_entry(monkeypatch):
    monkeypatch.setattr(
        panel_module,
        "run_control_center_panel_entry",
        lambda argv=None: 7,
    )

    assert _module_main(["--install-root", "C:\\Test"]) == 7
