from pathlib import Path
from types import SimpleNamespace

import pytest

from local_ai_control_center_installer import control_center_panel as panel_module
from local_ai_control_center_installer.control_center_panel import (
    _module_main,
    run_control_center_panel_entry,
)


def test_windowless_stream_guard_populates_missing_std_streams(tmp_path: Path, monkeypatch):
    fake_sys = SimpleNamespace(stdin=None, stdout=None, stderr=None)
    retained_streams: list[object] = []
    devnull_path = tmp_path / "devnull.txt"
    devnull_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(panel_module, "sys", fake_sys)
    monkeypatch.setattr(panel_module.os, "devnull", str(devnull_path))
    monkeypatch.setattr(panel_module, "_WINDOWLESS_STD_STREAMS", retained_streams)

    panel_module._ensure_std_streams_for_windowless_python()

    assert fake_sys.stdin is not None
    assert fake_sys.stdout is not None
    assert fake_sys.stderr is not None
    assert len(retained_streams) == 3


def test_panel_entry_prepares_windowless_streams_before_starting_uvicorn(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    calls: list[object] = []

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_panel._health_ready_for_install_root",
        lambda url, expected_install_root: False,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_panel._port_in_use",
        lambda host, port: False,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_panel._ensure_std_streams_for_windowless_python",
        lambda: calls.append("streams"),
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_panel.threading.Thread",
        lambda *args, **kwargs: SimpleNamespace(start=lambda: calls.append("thread")),
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_panel.uvicorn.run",
        lambda *args, **kwargs: calls.append(("uvicorn", kwargs)),
    )

    result = run_control_center_panel_entry(["--install-root", str(install_root)])

    assert result == 0
    assert calls[0] == "thread"
    assert calls[1] == "streams"
    assert calls[2][0] == "uvicorn"
    assert calls[2][1]["use_colors"] is False


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
        "local_ai_control_center_installer.control_center_panel._health_ready_for_install_root",
        lambda url, expected_install_root: False,
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


def test_panel_entry_ignores_open_browser_flag_when_panel_is_already_healthy(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    opened_urls: list[str] = []

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_panel._health_ready_for_install_root",
        lambda url, expected_install_root: True,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_panel._open_browser",
        lambda url: opened_urls.append(url),
    )

    result = run_control_center_panel_entry(
        ["--install-root", str(install_root), "--open-browser"]
    )

    assert result == 0
    assert opened_urls == ["http://127.0.0.1:3210/"]


def test_panel_entry_starts_browser_thread_when_open_browser_flag_is_requested(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    thread_targets: list[str] = []

    class FakeThread:
        def __init__(self, target=None, args=(), kwargs=None, daemon=None):
            self._target = target

        def start(self):
            thread_targets.append(self._target.__name__)

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_panel._health_ready_for_install_root",
        lambda url, expected_install_root: False,
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

    result = run_control_center_panel_entry(
        ["--install-root", str(install_root), "--open-browser"]
    )

    assert result == 0
    assert thread_targets == [
        "_ensure_runtime_ready_after_panel_boot",
        "_open_browser_when_ready",
    ]


def test_open_browser_when_ready_waits_for_matching_health_before_opening(monkeypatch):
    checks: list[str] = []
    opened_urls: list[str] = []

    def fake_health(url: str, *, expected_install_root: str) -> bool:
        checks.append(expected_install_root)
        return len(checks) >= 3

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_panel._health_ready_for_install_root",
        fake_health,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_panel._open_browser",
        lambda url: opened_urls.append(url),
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_panel.time.sleep",
        lambda seconds: None,
    )

    panel_module._open_browser_when_ready(
        "http://127.0.0.1:3210/",
        expected_install_root="C:\\RuntimePilot",
        timeout_seconds=1.0,
        poll_interval_seconds=0.01,
    )

    assert len(checks) == 3
    assert opened_urls == ["http://127.0.0.1:3210/"]


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

    with pytest.raises(RuntimeError, match="UI port 3210 je već zauzet drugim procesom."):
        run_control_center_panel_entry(["--install-root", str(install_root)])


def test_panel_module_main_delegates_to_entry(monkeypatch):
    monkeypatch.setattr(
        panel_module,
        "run_control_center_panel_entry",
        lambda argv=None: 7,
    )

    assert _module_main(["--install-root", "C:\\Test"]) == 7


def test_panel_open_browser_uses_startfile_fallback_on_windows(monkeypatch):
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(panel_module.os, "name", "nt", raising=False)
    monkeypatch.setattr(panel_module.webbrowser, "open", lambda url: False)
    monkeypatch.setattr(
        panel_module.os,
        "startfile",
        lambda url: calls.append(("startfile", url)),
        raising=False,
    )

    opened = panel_module._open_browser("http://127.0.0.1:3210/")

    assert opened is True
    assert calls == [("startfile", "http://127.0.0.1:3210/")]


def test_runtime_autostart_thread_warms_caches_after_ready(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    config = SimpleNamespace(install_root=install_root)
    calls: list[str] = []

    monkeypatch.setattr(panel_module, "get_config", lambda: config)
    monkeypatch.setattr(
        panel_module,
        "ensure_runtime_ready",
        lambda config: calls.append("ensure") or {"summary": "Runtime spreman."},
    )
    monkeypatch.setattr(
        panel_module,
        "_warm_control_center_caches",
        lambda config: calls.append("warm") or [],
    )

    panel_module._ensure_runtime_ready_after_panel_boot()

    log_text = (install_root / "logs" / "control-center-runtime-autostart.log").read_text(encoding="utf-8")
    assert calls == ["ensure", "warm"]
    assert "Runtime spreman." in log_text
    assert "Cache warmup completed." in log_text
