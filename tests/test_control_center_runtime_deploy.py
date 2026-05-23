from pathlib import Path

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
