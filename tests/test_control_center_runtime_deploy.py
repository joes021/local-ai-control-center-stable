from pathlib import Path
import subprocess

import pytest

from local_ai_control_center_installer.control_center_runtime import (
    ControlCenterRuntimeDeployment,
    PANEL_EXECUTABLE_NAME,
    _panel_health_ready,
    deploy_control_center_runtime,
    launch_control_center,
)


def _empty_shell_assets() -> dict[str, Path | str | None]:
    return {
        "opencode_launcher_path": None,
        "uninstall_launcher_path": None,
        "start_menu_dir": None,
        "start_menu_panel_shortcut_path": None,
        "start_menu_opencode_shortcut_path": None,
        "start_menu_uninstall_shortcut_path": None,
        "desktop_panel_shortcut_path": None,
        "desktop_opencode_shortcut_path": None,
        "uninstall_registry_key": None,
    }


def test_deploy_control_center_runtime_copies_current_frozen_executable_for_panel_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    install_root = tmp_path / "install-root"
    current_executable = tmp_path / "LocalAIControlCenterSetup-v0.1.13.exe"
    current_executable.write_bytes(b"panel-runtime")
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._ensure_windows_shell_assets",
        lambda **kwargs: _empty_shell_assets(),
    )

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


def test_launch_control_center_fails_fast_when_foreign_listener_occupies_ui_port(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    install_root = tmp_path / "install-root"
    deployment = ControlCenterRuntimeDeployment(
        install_root=install_root,
        panel_root=install_root / "control-center",
        executable_path=install_root / "control-center" / PANEL_EXECUTABLE_NAME,
        launcher_path=install_root / "control-center" / "Open-Control-Center.cmd",
        command=("fake-panel.exe", "--panel"),
        url="http://127.0.0.1:3210/",
        port=3210,
        access_mode="local-only",
        strategy="packaged-exe",
    )
    popen_calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._panel_health_ready",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._port_in_use",
        lambda host, port: True,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime.subprocess.Popen",
        lambda command, **kwargs: popen_calls.append(tuple(command)),
    )

    with pytest.raises(RuntimeError, match="UI port 3210 je već zauzet drugim procesom."):
        launch_control_center(deployment, timeout_seconds=0.1)

    assert popen_calls == []


def test_launch_control_center_reclaims_foreign_lacc_panel_port_and_starts_current_panel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    install_root = tmp_path / "install-root"
    deployment = ControlCenterRuntimeDeployment(
        install_root=install_root,
        panel_root=install_root / "control-center",
        executable_path=install_root / "control-center" / PANEL_EXECUTABLE_NAME,
        launcher_path=install_root / "control-center" / "Open-Control-Center.cmd",
        command=("fake-panel.exe", "--panel"),
        url="http://127.0.0.1:3210/",
        port=3210,
        access_mode="local-only",
        strategy="packaged-exe",
    )
    popen_calls: list[tuple[str, ...]] = []
    stop_calls: list[int] = []
    port_checks = iter([True, False])
    health_calls: list[str | None] = []

    def fake_panel_health_ready(url, *, expected_install_root=None):
        health_calls.append(expected_install_root)
        if expected_install_root == str(install_root):
            return len(health_calls) >= 3
        return True

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._panel_health_ready",
        fake_panel_health_ready,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._port_in_use",
        lambda host, port: next(port_checks),
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._find_listening_pid",
        lambda port, platform=None: 5151,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._stop_process_id",
        lambda pid, platform=None: stop_calls.append(pid) or None,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime.subprocess.Popen",
        lambda command, **kwargs: popen_calls.append(tuple(command)),
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime.time.sleep",
        lambda seconds: None,
    )

    result = launch_control_center(deployment, timeout_seconds=0.1)

    assert result == deployment
    assert stop_calls == [5151]
    assert popen_calls == [("fake-panel.exe", "--panel")]


def test_launch_control_center_uses_detached_windows_flags_for_panel_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    install_root = tmp_path / "install-root"
    deployment = ControlCenterRuntimeDeployment(
        install_root=install_root,
        panel_root=install_root / "control-center",
        executable_path=install_root / "control-center" / PANEL_EXECUTABLE_NAME,
        launcher_path=install_root / "control-center" / "Open-Control-Center.cmd",
        command=("fake-panel.exe", "--panel"),
        url="http://127.0.0.1:3210/",
        port=3210,
        access_mode="local-only",
        strategy="packaged-exe",
    )
    health_checks = {"count": 0}
    popen_kwargs: dict[str, object] = {}

    def fake_panel_health_ready(url, *, expected_install_root=None):
        if expected_install_root == str(install_root):
            health_checks["count"] += 1
            return health_checks["count"] >= 2
        return False

    def fake_popen(command, **kwargs):
        popen_kwargs.update(kwargs)
        return object()

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._panel_health_ready",
        fake_panel_health_ready,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._port_in_use",
        lambda host, port: False,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime.detached_subprocess_creationflags",
        lambda platform=None: 98765,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime.subprocess.Popen",
        fake_popen,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime.time.sleep",
        lambda seconds: None,
    )

    launch_control_center(deployment, timeout_seconds=0.1)

    assert popen_kwargs["creationflags"] == 98765


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
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._ensure_windows_shell_assets",
        lambda **kwargs: _empty_shell_assets(),
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
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._ensure_windows_shell_assets",
        lambda **kwargs: _empty_shell_assets(),
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


def test_deploy_control_center_runtime_tolerates_panel_process_already_gone(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    install_root = tmp_path / "install-root"
    current_executable = tmp_path / "LocalAIControlCenterSetup-v0.4.31.exe"
    current_executable.write_bytes(b"panel-runtime")
    copied_executable = install_root / "control-center" / PANEL_EXECUTABLE_NAME
    copied_executable.parent.mkdir(parents=True, exist_ok=True)
    copied_executable.write_bytes(b"old-panel-runtime")

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._panel_health_ready",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._find_panel_process_ids",
        lambda *args, **kwargs: [4242],
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._port_in_use",
        lambda host, port: False,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._stop_process_id",
        lambda pid, platform=None: 'ERROR: The process "4242" not found.',
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._ensure_windows_shell_assets",
        lambda **kwargs: _empty_shell_assets(),
    )

    deployment = deploy_control_center_runtime(
        install_root,
        panel_executable_resource=None,
        frozen=True,
        frozen_executable=str(current_executable),
    )

    assert deployment.strategy == "copied-frozen-exe"
    assert copied_executable.read_bytes() == b"panel-runtime"


def test_deploy_control_center_runtime_reuses_healthy_running_panel_when_binary_matches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    install_root = tmp_path / "install-root"
    current_executable = tmp_path / "LocalAIControlCenterSetup-v0.4.30.exe"
    current_executable.write_bytes(b"panel-runtime")
    copied_executable = install_root / "control-center" / PANEL_EXECUTABLE_NAME
    copied_executable.parent.mkdir(parents=True, exist_ok=True)
    copied_executable.write_bytes(b"panel-runtime")

    stop_calls: list[int] = []
    copy_calls: list[tuple[Path, Path]] = []

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._panel_health_ready",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._find_panel_process_ids",
        lambda *args, **kwargs: [4242],
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._port_in_use",
        lambda host, port: False,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._stop_process_id",
        lambda pid, platform=None: stop_calls.append(pid) or "ERROR: The process with PID 4242 could not be terminated.",
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._ensure_windows_shell_assets",
        lambda **kwargs: _empty_shell_assets(),
    )

    def fake_copy2(source, destination, *args, **kwargs):
        copy_calls.append((Path(source), Path(destination)))
        raise AssertionError("copy2 should not run when the panel binary already matches")

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
    assert stop_calls == []
    assert copy_calls == []
    assert copied_executable.read_bytes() == b"panel-runtime"


def test_deploy_control_center_runtime_creates_shell_shortcuts_and_uninstall_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    install_root = tmp_path / "install-root"
    current_executable = tmp_path / "LocalAIControlCenterSetup-v0.3.5.exe"
    current_executable.write_bytes(b"panel-runtime")

    start_menu_dir = tmp_path / "Start Menu" / "Programs" / "Local AI Control Center"
    desktop_dir = tmp_path / "Desktop"
    opencode_launcher_path = install_root / "control-center" / "Open-OpenCode.cmd"
    shortcut_calls: list[dict[str, object]] = []
    registry_call: dict[str, object] = {}

    def fake_prepare_opencode_launcher(config):
        opencode_launcher_path.parent.mkdir(parents=True, exist_ok=True)
        opencode_launcher_path.write_text("@echo off\r\n", encoding="utf-8")
        return opencode_launcher_path

    def fake_create_windows_shortcut(
        shortcut_path: Path,
        target_path: Path,
        *,
        working_directory: Path | None = None,
        description: str = "",
        icon_path: Path | None = None,
    ) -> None:
        shortcut_path.parent.mkdir(parents=True, exist_ok=True)
        shortcut_path.write_text(str(target_path), encoding="utf-8")
        shortcut_calls.append(
            {
                "shortcut_path": shortcut_path,
                "target_path": target_path,
                "working_directory": working_directory,
                "description": description,
                "icon_path": icon_path,
            }
        )

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime.prepare_opencode_launcher",
        fake_prepare_opencode_launcher,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._resolve_start_menu_programs_dir",
        lambda: start_menu_dir,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._resolve_desktop_dir",
        lambda: desktop_dir,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._create_windows_shortcut",
        fake_create_windows_shortcut,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime._register_uninstall_entry",
        lambda **kwargs: registry_call.update(kwargs),
    )

    deployment = deploy_control_center_runtime(
        install_root,
        panel_executable_resource=None,
        frozen=True,
        frozen_executable=str(current_executable),
    )

    assert deployment.opencode_launcher_path == opencode_launcher_path
    assert deployment.uninstall_launcher_path.is_file()
    assert deployment.start_menu_panel_shortcut_path == start_menu_dir / "Local AI Control Center.lnk"
    assert deployment.start_menu_opencode_shortcut_path == start_menu_dir / "OpenCode.lnk"
    assert deployment.start_menu_uninstall_shortcut_path == (
        start_menu_dir / "Uninstall Local AI Control Center.lnk"
    )
    assert deployment.desktop_panel_shortcut_path == desktop_dir / "Local AI Control Center.lnk"
    assert deployment.desktop_opencode_shortcut_path == desktop_dir / "OpenCode.lnk"
    assert len(shortcut_calls) == 5
    assert {call["shortcut_path"].name for call in shortcut_calls} == {
        "Local AI Control Center.lnk",
        "OpenCode.lnk",
        "Uninstall Local AI Control Center.lnk",
    }
    assert registry_call["install_root"] == install_root.resolve()
    assert registry_call["display_icon_path"] == deployment.executable_path
    assert registry_call["uninstall_command_path"] == deployment.uninstall_launcher_path
    assert registry_call["display_version"] == "0.3.5"
    uninstall_text = deployment.uninstall_launcher_path.read_text(encoding="utf-8")
    assert "Local AI Control Center uninstall je pokrenut." in uninstall_text
    assert str(install_root.resolve()) in uninstall_text


def test_deploy_control_center_runtime_creates_linux_python_host_and_launcher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    install_root = tmp_path / "install-root"
    opencode_launcher_path = install_root / "control-center" / "Open-OpenCode.sh"

    def fake_prepare_opencode_launcher(config, platform=None):
        opencode_launcher_path.parent.mkdir(parents=True, exist_ok=True)
        opencode_launcher_path.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        return opencode_launcher_path

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime.prepare_opencode_launcher",
        fake_prepare_opencode_launcher,
    )

    deployment = deploy_control_center_runtime(
        install_root,
        current_python="/usr/bin/python3",
        frozen=False,
        platform="linux",
    )

    host_path = install_root / "control-center" / "local-ai-control-center-panel"
    launcher_path = install_root / "control-center" / "Open-Control-Center.sh"
    host_text = host_path.read_text(encoding="utf-8")
    launcher_text = launcher_path.read_text(encoding="utf-8")

    assert deployment.strategy == "linux-python-host"
    assert deployment.executable_path == host_path
    assert deployment.launcher_path == launcher_path
    assert deployment.command[0] == str(host_path)
    assert deployment.opencode_launcher_path == opencode_launcher_path
    assert deployment.start_menu_dir is None
    assert deployment.desktop_panel_shortcut_path is None
    assert deployment.uninstall_registry_key is None
    assert host_text.startswith("#!/usr/bin/env bash\n")
    assert 'export LACC_INSTALL_ROOT="' in host_text
    assert 'exec "/usr/bin/python3" -m local_ai_control_center_installer.control_center_panel "$@"' in host_text
    assert launcher_text.startswith("#!/usr/bin/env bash\n")
    assert "nohup " in launcher_text
    assert "--open-browser" in launcher_text


def test_deploy_control_center_runtime_copies_linux_frozen_host_binary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    install_root = tmp_path / "install-root"
    current_executable = tmp_path / "local-ai-control-center-panel.bin"
    current_executable.write_bytes(b"panel-runtime")
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_runtime.prepare_opencode_launcher",
        lambda config: None,
    )

    deployment = deploy_control_center_runtime(
        install_root,
        panel_executable_resource=None,
        frozen=True,
        frozen_executable=str(current_executable),
        platform="linux",
    )

    copied_executable = install_root / "control-center" / "local-ai-control-center-panel"
    assert deployment.strategy == "copied-frozen-linux"
    assert deployment.executable_path == copied_executable
    assert copied_executable.read_bytes() == b"panel-runtime"
    assert deployment.command[0] == str(copied_executable)
    assert deployment.command[1] == "--panel"
    assert deployment.launcher_path.name == "Open-Control-Center.sh"
