from pathlib import Path
import subprocess

import pytest

from local_ai_control_center_installer.control_center_runtime import (
    PANEL_EXECUTABLE_NAME,
    _panel_health_ready,
    deploy_control_center_runtime,
)


def test_deploy_control_center_runtime_copies_current_frozen_executable_for_panel_runtime(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    current_executable = tmp_path / "LocalAIControlCenterSetup-v0.1.13.exe"
    current_executable.write_bytes(b"panel-runtime")

    deployment = deploy_control_center_runtime(
        install_root,
        panel_executable_resource=None,
        frozen=True,
        frozen_executable=str(current_executable),
    )

    copied_executable = install_root / "control-center" / PANEL_EXECUTABLE_NAME
    assert deployment.strategy == "copied-frozen-exe"
    assert deployment.executable_path == copied_executable
    assert copied_executable.read_bytes() == b"panel-runtime"
    assert deployment.command[0] == str(copied_executable)
    assert deployment.command[1] == "--panel"
    assert deployment.launcher_path.is_file()


def test_panel_health_ready_rejects_foreign_service_payload(monkeypatch: pytest.MonkeyPatch):
    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"status":"ok","app":"something-else","installRoot":"C:\\\\Other"}'

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime.urlopen",
        lambda *args, **kwargs: FakeResponse(),
    )

    assert _panel_health_ready(
        "http://127.0.0.1:3210/",
        expected_install_root="C:\\PanelRoot",
    ) is False


def test_deploy_control_center_runtime_stops_existing_panel_before_replacing_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    install_root = tmp_path / "install-root"
    current_executable = tmp_path / "LocalAIControlCenterSetup-v0.3.1.exe"
    current_executable.write_bytes(b"panel-runtime")
    copied_executable = install_root / "control-center" / PANEL_EXECUTABLE_NAME
    copied_executable.parent.mkdir(parents=True, exist_ok=True)
    copied_executable.write_bytes(b"old-panel-runtime")

    taskkill_calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._panel_health_ready",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._find_panel_process_ids",
        lambda executable_path: [4242, 4343],
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._port_in_use",
        lambda host, port: False,
    )

    def fake_run(command, **kwargs):
        taskkill_calls.append(tuple(command))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime.subprocess.run",
        fake_run,
    )

    deployment = deploy_control_center_runtime(
        install_root,
        panel_executable_resource=None,
        frozen=True,
        frozen_executable=str(current_executable),
    )

    assert deployment.strategy == "copied-frozen-exe"
    assert copied_executable.read_bytes() == b"panel-runtime"
    assert taskkill_calls == [
        ("taskkill", "/PID", "4242", "/F"),
        ("taskkill", "/PID", "4343", "/F"),
    ]


def test_deploy_control_center_runtime_retries_copy_after_panel_executable_unlocks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    install_root = tmp_path / "install-root"
    current_executable = tmp_path / "LocalAIControlCenterSetup-v0.3.1.exe"
    current_executable.write_bytes(b"panel-runtime")
    copied_executable = install_root / "control-center" / PANEL_EXECUTABLE_NAME
    copied_executable.parent.mkdir(parents=True, exist_ok=True)
    copied_executable.write_bytes(b"old-panel-runtime")

    copy_attempts = {"count": 0}
    wait_calls: list[Path] = []

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._panel_health_ready",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._find_panel_process_ids",
        lambda executable_path: [4242, 4343],
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._port_in_use",
        lambda host, port: False,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout="", stderr=""),
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._wait_for_path_replaceable",
        lambda path, timeout_seconds=10.0: wait_calls.append(path),
    )

    def fake_copy2(source, destination, *args, **kwargs):
        copy_attempts["count"] += 1
        if copy_attempts["count"] == 1:
            raise PermissionError(32, "The process cannot access the file because it is being used by another process")
        Path(destination).write_bytes(Path(source).read_bytes())
        return str(destination)

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime.shutil.copy2",
        fake_copy2,
    )

    deployment = deploy_control_center_runtime(
        install_root,
        panel_executable_resource=None,
        frozen=True,
        frozen_executable=str(current_executable),
    )

    assert deployment.strategy == "copied-frozen-exe"
    assert copy_attempts["count"] == 2
    assert wait_calls == [copied_executable]
    assert copied_executable.read_bytes() == b"panel-runtime"
