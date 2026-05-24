from pathlib import Path
import subprocess

from local_ai_control_center_installer.control_center_backend.services import system_service


def test_pick_working_directory_reports_missing_linux_picker(monkeypatch):
    monkeypatch.setattr(system_service, "is_windows_platform", lambda platform=None: False)
    monkeypatch.setattr(system_service.shutil, "which", lambda name: None)

    result = system_service.pick_working_directory()

    assert result["status"] == "error"
    assert "zenity" in result["summary"].lower()


def test_pick_local_gguf_uses_zenity_on_linux(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(system_service, "is_windows_platform", lambda platform=None: False)
    monkeypatch.setattr(
        system_service.shutil,
        "which",
        lambda name: "/usr/bin/zenity" if name == "zenity" else None,
    )

    def fake_run(command, **kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout="/models/demo.gguf\n", stderr="")

    monkeypatch.setattr(system_service.subprocess, "run", fake_run)

    result = system_service.pick_local_gguf()

    assert result["status"] == "ok"
    assert result["path"] == "/models/demo.gguf"
    assert captured["command"][:2] == ["zenity", "--file-selection"]
