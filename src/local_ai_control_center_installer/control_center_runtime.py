from __future__ import annotations
from dataclasses import dataclass
from importlib.resources import files
from importlib.metadata import PackageNotFoundError, version as package_version
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import stat
import shlex
import re
from urllib.error import URLError
from urllib.request import urlopen

from local_ai_control_center_installer.control_center_backend.config import (
    ControlCenterConfig,
    DEFAULT_INSTALL_ROOT,
)
from local_ai_control_center_installer.control_center_backend.services.opencode_service import (
    prepare_opencode_launcher,
)
from local_ai_control_center_installer.control_center_uninstall import (
    LEGACY_PANEL_SHORTCUT_NAMES,
    LEGACY_START_MENU_FOLDER_NAMES,
    LEGACY_UNINSTALL_SHORTCUT_NAMES,
    OPENCODE_SHORTCUT_NAME,
    PANEL_SHORTCUT_NAME,
    START_MENU_FOLDER_NAME,
    UNINSTALL_REGISTRY_KEY,
    UNINSTALL_SHORTCUT_NAME,
)
from local_ai_control_center_installer.platform_paths import (
    detached_subprocess_creationflags,
    hidden_subprocess_creationflags,
    is_windows_platform,
)
from local_ai_control_center_installer.session import InstallerSession


WINDOWS_PANEL_EXECUTABLE_NAME = "RuntimePilotPanel.exe"
WINDOWS_PANEL_STARTUP_SPLASH_NAME = "RuntimePilot-Startup.hta"
WINDOWS_PANEL_STARTUP_SCRIPT_NAME = "RuntimePilot-Startup.pyw"
LINUX_PANEL_HOST_NAME = "local-ai-control-center-panel"
WINDOWS_UNINSTALL_LAUNCHER_NAME = "Uninstall-RuntimePilot.cmd"
LINUX_UNINSTALL_LAUNCHER_NAME = "Uninstall-RuntimePilot.sh"
PANEL_EXECUTABLE_NAME = WINDOWS_PANEL_EXECUTABLE_NAME
UNINSTALL_LAUNCHER_NAME = WINDOWS_UNINSTALL_LAUNCHER_NAME
DEFAULT_PANEL_PORT = 3210
DEFAULT_PANEL_URL = f"http://127.0.0.1:{DEFAULT_PANEL_PORT}/"
WINDOWS_PANEL_ICON_RESOURCE = "assets/windows/runtimepilot-icon.ico"
WINDOWS_PANEL_ICON_NAME = "RuntimePilot.ico"
WINDOWS_OPENCODE_ICON_RESOURCE = "assets/windows/runtimepilot-opencode-icon.ico"
WINDOWS_OPENCODE_ICON_NAME = "RuntimePilot-OpenCode.ico"


@dataclass(frozen=True)
class ControlCenterRuntimeDeployment:
    install_root: Path
    panel_root: Path
    executable_path: Path
    launcher_path: Path
    command: tuple[str, ...]
    url: str
    port: int
    access_mode: str
    strategy: str
    env_overrides: dict[str, str] | None = None
    opencode_launcher_path: Path | None = None
    uninstall_launcher_path: Path | None = None
    start_menu_dir: Path | None = None
    start_menu_panel_shortcut_path: Path | None = None
    start_menu_opencode_shortcut_path: Path | None = None
    start_menu_uninstall_shortcut_path: Path | None = None
    desktop_panel_shortcut_path: Path | None = None
    desktop_opencode_shortcut_path: Path | None = None
    uninstall_registry_key: str | None = None


def _is_windows_runtime_platform(platform: str | None = None) -> bool:
    normalized = (platform or sys.platform).strip().lower()
    return is_windows_platform(normalized)


def _panel_host_name_for_platform(platform: str | None = None) -> str:
    if _is_windows_runtime_platform(platform):
        return WINDOWS_PANEL_EXECUTABLE_NAME
    return LINUX_PANEL_HOST_NAME


def _panel_launcher_name_for_platform(platform: str | None = None) -> str:
    if _is_windows_runtime_platform(platform):
        return "Open-RuntimePilot.cmd"
    return "Open-RuntimePilot.sh"


def _uninstall_launcher_name_for_platform(platform: str | None = None) -> str:
    if _is_windows_runtime_platform(platform):
        return WINDOWS_UNINSTALL_LAUNCHER_NAME
    return LINUX_UNINSTALL_LAUNCHER_NAME


def deploy_control_center_runtime(
    install_root: str | Path,
    *,
    panel_executable_resource: Path | None = None,
    current_python: str | None = None,
    frozen: bool | None = None,
    frozen_executable: str | Path | None = None,
    platform: str | None = None,
) -> ControlCenterRuntimeDeployment:
    normalized_install_root = Path(install_root).expanduser().resolve()
    panel_root = normalized_install_root / "control-center"
    panel_root.mkdir(parents=True, exist_ok=True)
    launcher_path = panel_root / _panel_launcher_name_for_platform(platform)
    panel_host_path = panel_root / _panel_host_name_for_platform(platform)
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))

    panel_executable_resource = panel_executable_resource or _resolve_panel_executable_resource()
    candidate_frozen_executable = (
        Path(frozen_executable).expanduser().resolve()
        if frozen_executable is not None
        else Path(sys.executable).resolve()
    )
    panel_binary_source = _resolve_panel_binary_source(
        panel_executable_resource=panel_executable_resource,
        frozen=frozen,
        candidate_frozen_executable=candidate_frozen_executable,
        platform=platform,
    )
    _stop_existing_panel_for_update(
        install_root=normalized_install_root,
        port=DEFAULT_PANEL_PORT,
        panel_executable_path=panel_host_path,
        replacement_panel_path=panel_binary_source,
        platform=platform,
    )
    if (
        panel_executable_resource is not None
        and panel_executable_resource.is_file()
        and _is_windows_runtime_platform(platform)
    ):
        executable_path = panel_host_path
        _copy_panel_executable(panel_executable_resource, executable_path)
        command = (
            str(executable_path),
            "--install-root",
            str(normalized_install_root),
            "--host",
            "127.0.0.1",
            "--port",
            str(DEFAULT_PANEL_PORT),
            "--access-mode",
            "local-only",
        )
        _write_launcher_script(
            launcher_path,
            command,
            env_overrides=None,
            platform=platform,
        )
        shell_assets = _ensure_windows_shell_assets(
            install_root=normalized_install_root,
            panel_root=panel_root,
            panel_launcher_path=launcher_path,
            panel_executable_path=executable_path,
            access_mode="local-only",
            display_version=_resolve_display_version(panel_executable_resource),
        )
        return ControlCenterRuntimeDeployment(
            install_root=normalized_install_root,
            panel_root=panel_root,
            executable_path=executable_path,
            launcher_path=launcher_path,
            command=command,
            url=DEFAULT_PANEL_URL,
            port=DEFAULT_PANEL_PORT,
            access_mode="local-only",
            strategy="packaged-exe",
            opencode_launcher_path=shell_assets["opencode_launcher_path"],
            uninstall_launcher_path=shell_assets["uninstall_launcher_path"],
            start_menu_dir=shell_assets["start_menu_dir"],
            start_menu_panel_shortcut_path=shell_assets["start_menu_panel_shortcut_path"],
            start_menu_opencode_shortcut_path=shell_assets["start_menu_opencode_shortcut_path"],
            start_menu_uninstall_shortcut_path=shell_assets["start_menu_uninstall_shortcut_path"],
            desktop_panel_shortcut_path=shell_assets["desktop_panel_shortcut_path"],
            desktop_opencode_shortcut_path=shell_assets["desktop_opencode_shortcut_path"],
            uninstall_registry_key=shell_assets["uninstall_registry_key"],
        )

    if frozen and candidate_frozen_executable.is_file():
        executable_path = panel_host_path
        _copy_panel_executable(candidate_frozen_executable, executable_path)
        if not _is_windows_runtime_platform(platform):
            command = (
                str(executable_path),
                "--panel",
                "--install-root",
                str(normalized_install_root),
                "--host",
                "127.0.0.1",
                "--port",
                str(DEFAULT_PANEL_PORT),
                "--access-mode",
                "local-only",
            )
            _write_launcher_script(
                launcher_path,
                command,
                env_overrides=None,
                platform=platform,
            )
            shell_assets = _ensure_linux_shell_assets(
                install_root=normalized_install_root,
                panel_root=panel_root,
                launcher_path=launcher_path,
                access_mode="local-only",
            )
            return ControlCenterRuntimeDeployment(
                install_root=normalized_install_root,
                panel_root=panel_root,
                executable_path=executable_path,
                launcher_path=launcher_path,
                command=command,
                url=DEFAULT_PANEL_URL,
                port=DEFAULT_PANEL_PORT,
                access_mode="local-only",
                strategy="copied-frozen-linux",
                opencode_launcher_path=shell_assets["opencode_launcher_path"],
                uninstall_launcher_path=shell_assets["uninstall_launcher_path"],
                start_menu_dir=None,
                start_menu_panel_shortcut_path=None,
                start_menu_opencode_shortcut_path=None,
                start_menu_uninstall_shortcut_path=None,
                desktop_panel_shortcut_path=None,
                desktop_opencode_shortcut_path=None,
                uninstall_registry_key=None,
            )

        command = (
            str(executable_path),
            "--panel",
            "--install-root",
            str(normalized_install_root),
            "--host",
            "127.0.0.1",
            "--port",
            str(DEFAULT_PANEL_PORT),
            "--access-mode",
            "local-only",
        )
        _write_launcher_script(
            launcher_path,
            command,
            env_overrides=None,
            platform=platform,
        )
        shell_assets = _ensure_windows_shell_assets(
            install_root=normalized_install_root,
            panel_root=panel_root,
            panel_launcher_path=launcher_path,
            panel_executable_path=executable_path,
            access_mode="local-only",
            display_version=_resolve_display_version(candidate_frozen_executable),
        )
        return ControlCenterRuntimeDeployment(
            install_root=normalized_install_root,
            panel_root=panel_root,
            executable_path=executable_path,
            launcher_path=launcher_path,
            command=command,
            url=DEFAULT_PANEL_URL,
            port=DEFAULT_PANEL_PORT,
            access_mode="local-only",
            strategy="copied-frozen-exe",
            opencode_launcher_path=shell_assets["opencode_launcher_path"],
            uninstall_launcher_path=shell_assets["uninstall_launcher_path"],
            start_menu_dir=shell_assets["start_menu_dir"],
            start_menu_panel_shortcut_path=shell_assets["start_menu_panel_shortcut_path"],
            start_menu_opencode_shortcut_path=shell_assets["start_menu_opencode_shortcut_path"],
            start_menu_uninstall_shortcut_path=shell_assets["start_menu_uninstall_shortcut_path"],
            desktop_panel_shortcut_path=shell_assets["desktop_panel_shortcut_path"],
            desktop_opencode_shortcut_path=shell_assets["desktop_opencode_shortcut_path"],
            uninstall_registry_key=shell_assets["uninstall_registry_key"],
        )

    python_executable = current_python or sys.executable
    src_root = Path(__file__).resolve().parents[1]
    env_overrides = {
        "LACC_INSTALL_ROOT": str(normalized_install_root),
        "LACC_UI_PORT": str(DEFAULT_PANEL_PORT),
        "LACC_UI_ACCESS_MODE": "local-only",
        "PYTHONPATH": str(src_root),
    }
    if not _is_windows_runtime_platform(platform):
        executable_path = panel_host_path
        _write_linux_panel_host_script(
            executable_path=executable_path,
            python_executable=python_executable,
            install_root=normalized_install_root,
            src_root=src_root,
        )
        command = (
            str(executable_path),
            "--install-root",
            str(normalized_install_root),
            "--host",
            "127.0.0.1",
            "--port",
            str(DEFAULT_PANEL_PORT),
            "--access-mode",
            "local-only",
        )
        _write_launcher_script(
            launcher_path,
            command,
            env_overrides=None,
            platform=platform,
        )
        shell_assets = _ensure_linux_shell_assets(
            install_root=normalized_install_root,
            panel_root=panel_root,
            launcher_path=launcher_path,
            access_mode="local-only",
        )
        return ControlCenterRuntimeDeployment(
            install_root=normalized_install_root,
            panel_root=panel_root,
            executable_path=executable_path,
            launcher_path=launcher_path,
            command=command,
            url=DEFAULT_PANEL_URL,
            port=DEFAULT_PANEL_PORT,
            access_mode="local-only",
            strategy="linux-python-host",
            env_overrides=None,
            opencode_launcher_path=shell_assets["opencode_launcher_path"],
            uninstall_launcher_path=shell_assets["uninstall_launcher_path"],
            start_menu_dir=None,
            start_menu_panel_shortcut_path=None,
            start_menu_opencode_shortcut_path=None,
            start_menu_uninstall_shortcut_path=None,
            desktop_panel_shortcut_path=None,
            desktop_opencode_shortcut_path=None,
            uninstall_registry_key=None,
        )

    command = (
        python_executable,
        "-m",
        "local_ai_control_center_installer.control_center_panel",
        "--install-root",
        str(normalized_install_root),
        "--host",
        "127.0.0.1",
        "--port",
        str(DEFAULT_PANEL_PORT),
        "--access-mode",
        "local-only",
    )
    _write_launcher_script(
        launcher_path,
        command,
        env_overrides=env_overrides,
        platform=platform,
    )
    startup_script_path = panel_root / WINDOWS_PANEL_STARTUP_SCRIPT_NAME
    _write_windows_python_startup_script(
        startup_script_path=startup_script_path,
        install_root=normalized_install_root,
        src_root=src_root,
    )
    startup_shortcut_target, startup_shortcut_arguments = _build_windows_python_startup_shortcut_spec(
        python_executable=Path(python_executable),
        startup_script_path=startup_script_path,
    )
    shell_assets = _ensure_windows_shell_assets(
        install_root=normalized_install_root,
        panel_root=panel_root,
        panel_launcher_path=launcher_path,
        panel_executable_path=Path(python_executable),
        access_mode="local-only",
        display_version=_resolve_display_version(Path(python_executable)),
        startup_shortcut_target=startup_shortcut_target,
        startup_shortcut_arguments=startup_shortcut_arguments,
    )
    return ControlCenterRuntimeDeployment(
        install_root=normalized_install_root,
        panel_root=panel_root,
        executable_path=Path(python_executable),
        launcher_path=launcher_path,
        command=command,
        url=DEFAULT_PANEL_URL,
        port=DEFAULT_PANEL_PORT,
        access_mode="local-only",
        strategy="python-fallback",
        env_overrides=env_overrides,
        opencode_launcher_path=shell_assets["opencode_launcher_path"],
        uninstall_launcher_path=shell_assets["uninstall_launcher_path"],
        start_menu_dir=shell_assets["start_menu_dir"],
        start_menu_panel_shortcut_path=shell_assets["start_menu_panel_shortcut_path"],
        start_menu_opencode_shortcut_path=shell_assets["start_menu_opencode_shortcut_path"],
        start_menu_uninstall_shortcut_path=shell_assets["start_menu_uninstall_shortcut_path"],
        desktop_panel_shortcut_path=shell_assets["desktop_panel_shortcut_path"],
        desktop_opencode_shortcut_path=shell_assets["desktop_opencode_shortcut_path"],
        uninstall_registry_key=shell_assets["uninstall_registry_key"],
    )


def apply_control_center_integration(
    session: InstallerSession,
    *,
    current_python: str | None = None,
    panel_executable_resource: Path | None = None,
    frozen: bool | None = None,
    frozen_executable: str | Path | None = None,
    launch_timeout_seconds: float = 30.0,
) -> InstallerSession:
    if session.first_run_status != "ready":
        session.control_center_runtime_status = "skipped"
        session.control_center_launch_status = "skipped"
        return session

    install_root = (session.install_root or "").strip()
    if not install_root:
        session.control_center_runtime_status = "failed"
        session.control_center_launch_status = "failed"
        session.failing_step = session.failing_step or "control-center-runtime"
        session.error_message = session.error_message or "Install root is required."
        return session

    try:
        deployment = deploy_control_center_runtime(
            install_root,
            panel_executable_resource=panel_executable_resource,
            current_python=current_python,
            frozen=frozen,
            frozen_executable=frozen_executable,
        )
        session.control_center_runtime_status = "ready"
        session.control_center_executable_path = str(deployment.executable_path)
        session.control_center_launcher_path = str(deployment.launcher_path)
        session.control_center_url = deployment.url
        session.control_center_port = deployment.port
    except Exception as exc:
        session.control_center_runtime_status = "failed"
        session.control_center_launch_status = "failed"
        session.failing_step = session.failing_step or "control-center-runtime"
        session.error_message = str(exc)
        return session

    try:
        launch_control_center(deployment, timeout_seconds=launch_timeout_seconds)
    except Exception as exc:
        session.control_center_launch_status = "failed"
        session.failing_step = session.failing_step or "control-center-launch"
        session.error_message = str(exc)
        return session

    session.control_center_launch_status = "ready"
    return session


def launch_control_center(
    deployment: ControlCenterRuntimeDeployment,
    *,
    timeout_seconds: float = 30.0,
) -> ControlCenterRuntimeDeployment:
    if _panel_health_ready(
        deployment.url,
        expected_install_root=str(deployment.install_root),
    ):
        return deployment
    if _port_in_use("127.0.0.1", deployment.port):
        if _panel_health_ready(deployment.url):
            listening_pid = _find_listening_pid(deployment.port)
            if listening_pid is None:
                raise RuntimeError(
                    f"UI port {deployment.port} je već zauzet drugim RuntimePilot procesom."
                )
            detail = _stop_process_id(listening_pid)
            if detail is not None:
                raise RuntimeError(
                    f"RuntimePilot panel nije mogao da preuzme port {deployment.port}: {detail}"
                )
            _wait_for_port_release("127.0.0.1", deployment.port)
        else:
            raise RuntimeError(f"UI port {deployment.port} je već zauzet drugim procesom.")

    environment = os.environ.copy()
    if deployment.env_overrides:
        environment.update(deployment.env_overrides)
    subprocess.Popen(
        list(deployment.command),
        cwd=str(deployment.install_root),
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=detached_subprocess_creationflags(),
        close_fds=False,
    )

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _panel_health_ready(
            deployment.url,
            expected_install_root=str(deployment.install_root),
        ):
            return deployment
        time.sleep(0.5)

    raise TimeoutError("RuntimePilot panel nije odgovorio na /health u predvidjenom roku.")


def _resolve_panel_executable_resource() -> Path | None:
    try:
        resource = files("local_ai_control_center_installer.panel_runtime").joinpath(
            PANEL_EXECUTABLE_NAME
        )
    except ModuleNotFoundError:
        return None
    resource_path = Path(str(resource))
    if resource_path.is_file():
        return resource_path
    return None


def _install_windows_shell_icon(
    *,
    panel_root: Path,
    resource_path: str,
    installed_name: str,
    fallback_icon_path: Path | None = None,
) -> Path | None:
    installed_icon_path = panel_root / installed_name
    try:
        icon_bytes = (
            files("local_ai_control_center_installer")
            .joinpath(resource_path)
            .read_bytes()
        )
    except (FileNotFoundError, ModuleNotFoundError):
        if fallback_icon_path is not None and fallback_icon_path.is_file():
            return fallback_icon_path
        return None
    installed_icon_path.write_bytes(icon_bytes)
    return installed_icon_path


def _write_launcher_script(
    launcher_path: Path,
    command: tuple[str, ...],
    *,
    env_overrides: dict[str, str] | None,
    platform: str | None = None,
) -> None:
    if not _is_windows_runtime_platform(platform):
        launcher_path.parent.mkdir(parents=True, exist_ok=True)
        quoted_command = " ".join(shlex.quote(part) for part in command)
        lines = [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
        ]
        for key, value in (env_overrides or {}).items():
            lines.append(f'export {key}="{value}"')
        lines.append(f"nohup {quoted_command} >/dev/null 2>&1 &")
        launcher_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        _ensure_executable_bit(launcher_path)
        return

    launcher_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["@echo off"]
    for key, value in (env_overrides or {}).items():
        lines.append(f"set \"{key}={value}\"")
    lines.extend(_build_windows_panel_launcher_guard_lines(command))
    lines.append(_build_windows_panel_background_launch_line(command))
    launcher_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")


def _build_windows_panel_launcher_guard_lines(command: tuple[str, ...]) -> list[str]:
    install_root = _extract_command_flag_value(command, "--install-root")
    port = _extract_command_flag_value(command, "--port")
    host = _extract_command_flag_value(command, "--host") or "127.0.0.1"
    if not install_root or not port:
        return []
    normalized_install_root = str(Path(install_root).expanduser().resolve())
    health_url = f"http://{host}:{port}/health"
    panel_process_guard = _build_windows_panel_process_guard(command, normalized_install_root)
    powershell_script = (
        f"$installRoot = {_quote_powershell_string(normalized_install_root)}; "
        f"$healthUrl = {_quote_powershell_string(health_url)}; "
        "try { "
        "  $response = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 1; "
        "  $actualInstallRoot = [System.IO.Path]::GetFullPath([string]$response.installRoot).ToLowerInvariant(); "
        "  $expectedInstallRoot = [System.IO.Path]::GetFullPath($installRoot).ToLowerInvariant(); "
        "  if ($response.status -eq 'ok' -and $response.app -eq 'local-ai-control-center-stable' -and $actualInstallRoot -eq $expectedInstallRoot) { exit 0 } "
        "} catch {} ; "
        f"{panel_process_guard}"
        "exit 1"
    )
    return [
        f'powershell -NoProfile -ExecutionPolicy Bypass -Command "{powershell_script}" >nul 2>nul',
        'if "%ERRORLEVEL%"=="0" exit /b 0',
        'if "%ERRORLEVEL%"=="10" (',
        '  echo Launch RuntimePilot je vec u toku.',
        '  exit /b 0',
        ")",
    ]


def _build_windows_panel_process_guard(
    command: tuple[str, ...],
    normalized_install_root: str,
) -> str:
    if _is_python_panel_module_command(command):
        python_executable = Path(str(command[0])).expanduser().resolve()
        pythonw_executable = _resolve_windows_background_python_executable(python_executable)
        command_token = "local_ai_control_center_installer.control_center_panel"
        port = _extract_command_flag_value(command, "--port") or str(DEFAULT_PANEL_PORT)
        return (
            f"$pythonExe = {_quote_powershell_string(str(python_executable))}; "
            f"$pythonwExe = {_quote_powershell_string(str(pythonw_executable))}; "
            f"$commandToken = {_quote_powershell_string(command_token)}; "
            f"$expectedPort = {_quote_powershell_string(port)}; "
            "$panelMatches = Get-CimInstance Win32_Process "
            "| Where-Object { "
            "  ($_.ExecutablePath -eq $pythonExe -or $_.ExecutablePath -eq $pythonwExe) "
            "  -and $_.CommandLine -like ('*' + $commandToken + '*') "
            "  -and $_.CommandLine -like ('*' + $installRoot + '*') "
            "  -and $_.CommandLine -like ('*--port ' + $expectedPort + '*') "
            "}; "
            "if (($panelMatches | Measure-Object).Count -gt 0) { exit 10 }; "
        )
    panel_executable = Path(str(command[0])).expanduser().resolve()
    return (
        f"$panelExe = {_quote_powershell_string(str(panel_executable))}; "
        "$panelMatches = Get-CimInstance Win32_Process "
        "| Where-Object { $_.ExecutablePath -eq $panelExe }; "
        "if (($panelMatches | Measure-Object).Count -gt 0) { exit 10 }; "
    )


def _build_windows_browser_watcher_command(
    *,
    panel_url: str,
    expected_install_root: Path,
    marker_path: Path,
) -> str:
    health_url = f"{panel_url.rstrip('/')}/health"
    normalized_install_root = str(expected_install_root.expanduser().resolve())
    normalized_marker_path = str(marker_path.expanduser().resolve())
    powershell_script = (
        f"$targetUrl = {_quote_powershell_string(panel_url)}; "
        f"$healthUrl = {_quote_powershell_string(health_url)}; "
        f"$markerPath = {_quote_powershell_string(normalized_marker_path)}; "
        f"$installRoot = {_quote_powershell_string(normalized_install_root)}; "
        "for ($attempt = 0; $attempt -lt 45; $attempt++) { "
        "  if (Test-Path $markerPath) { exit 0 } "
        "  try { "
        "    $response = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2; "
        "    $actualInstallRoot = [System.IO.Path]::GetFullPath([string]$response.installRoot).ToLowerInvariant(); "
        "    $expectedInstallRoot = [System.IO.Path]::GetFullPath($installRoot).ToLowerInvariant(); "
        "    if ($response.status -eq 'ok' -and $response.app -eq 'local-ai-control-center-stable' -and $actualInstallRoot -eq $expectedInstallRoot) { "
        "      Start-Process $targetUrl; "
        "      Set-Content -Path $markerPath -Value 'opened' -Encoding UTF8; "
        "      exit 0 "
        "    } "
        "  } catch {} "
        "  Start-Sleep -Milliseconds 900 "
        "} "
        "exit 1"
    )
    return f'powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -Command "{powershell_script}"'


def _build_windows_python_startup_shortcut_spec(
    *,
    python_executable: Path,
    startup_script_path: Path,
) -> tuple[Path, str]:
    background_python = _resolve_windows_background_python_executable(
        python_executable.expanduser().resolve()
    )
    arguments = f'"{startup_script_path.expanduser().resolve()}"'
    return background_python, arguments


def _write_windows_python_startup_script(
    *,
    startup_script_path: Path,
    install_root: Path,
    src_root: Path,
) -> None:
    startup_script_path.parent.mkdir(parents=True, exist_ok=True)
    script = "\n".join(
        [
            "from pathlib import Path",
            "import sys",
            "",
            f"SRC_ROOT = Path({str(src_root.resolve())!r})",
            f"INSTALL_ROOT = Path({str(install_root.resolve())!r})",
            "",
            "if str(SRC_ROOT) not in sys.path:",
            "    sys.path.insert(0, str(SRC_ROOT))",
            "",
            "from local_ai_control_center_installer.control_center_startup import (",
            "    run_control_center_startup_entry,",
            ")",
            "",
            "raise SystemExit(",
            "    run_control_center_startup_entry([",
            '        "--install-root",',
            "        str(INSTALL_ROOT),",
            "    ])",
            ")",
            "",
        ]
    )
    startup_script_path.write_text(script, encoding="utf-8")


def _is_python_panel_module_command(command: tuple[str, ...]) -> bool:
    return len(command) >= 3 and str(command[1]).strip() == "-m" and str(command[2]).strip() == "local_ai_control_center_installer.control_center_panel"


def _resolve_windows_background_python_executable(python_executable: Path) -> Path:
    if python_executable.name.casefold() == "python.exe":
        candidate = python_executable.with_name("pythonw.exe")
        if candidate.is_file():
            return candidate
    return python_executable


def _build_windows_panel_background_launch_line(command: tuple[str, ...]) -> str:
    launch_parts = list(command)
    if _is_python_panel_module_command(command):
        background_python = _resolve_windows_background_python_executable(
            Path(str(command[0])).expanduser().resolve()
        )
        launch_parts[0] = str(background_python)
    quoted_command = " ".join(_quote_windows_part(str(part)) for part in launch_parts)
    return f'start "" /b {quoted_command}'


def _extract_command_flag_value(command: tuple[str, ...], flag: str) -> str | None:
    try:
        index = command.index(flag)
    except ValueError:
        return None
    if index + 1 >= len(command):
        return None
    return str(command[index + 1] or "").strip() or None


def _write_linux_panel_host_script(
    *,
    executable_path: Path,
    python_executable: str | Path,
    install_root: Path,
    src_root: Path,
) -> None:
    executable_path.parent.mkdir(parents=True, exist_ok=True)
    python_command = (
        python_executable
        if isinstance(python_executable, str)
        else str(python_executable)
    )
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        f'export LACC_INSTALL_ROOT="{install_root}"',
        f'export LACC_UI_PORT="{DEFAULT_PANEL_PORT}"',
        'export LACC_UI_ACCESS_MODE="local-only"',
        f'export PYTHONPATH="{src_root}${{PYTHONPATH:+:${{PYTHONPATH}}}}"',
        f'exec "{python_command}" -m local_ai_control_center_installer.control_center_panel "$@"',
    ]
    executable_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _ensure_executable_bit(executable_path)


def _ensure_linux_shell_assets(
    *,
    install_root: Path,
    panel_root: Path,
    launcher_path: Path,
    access_mode: str,
) -> dict[str, Path | str | None]:
    config = ControlCenterConfig(
        ui_host="127.0.0.1",
        ui_port=DEFAULT_PANEL_PORT,
        install_root=install_root,
        access_mode=access_mode,
    )
    try:
        opencode_launcher_path = _prepare_opencode_launcher_for_platform(
            config=config,
            platform="linux",
        )
    except FileNotFoundError:
        opencode_launcher_path = None

    uninstall_launcher_path = panel_root / _uninstall_launcher_name_for_platform("linux")
    _write_linux_uninstall_launcher(uninstall_launcher_path, install_root=install_root)
    return {
        "opencode_launcher_path": opencode_launcher_path,
        "uninstall_launcher_path": uninstall_launcher_path,
    }


def _prepare_opencode_launcher_for_platform(
    *,
    config: ControlCenterConfig,
    platform: str,
) -> Path:
    try:
        return prepare_opencode_launcher(config=config, platform=platform)
    except TypeError:
        return prepare_opencode_launcher(config=config)


def _ensure_windows_shell_assets(
    *,
    install_root: Path,
    panel_root: Path,
    panel_launcher_path: Path,
    panel_executable_path: Path,
    access_mode: str,
    display_version: str,
    startup_shortcut_target: Path | None = None,
    startup_shortcut_arguments: str = "",
) -> dict[str, Path | str | None]:
    config = ControlCenterConfig(
        ui_host="127.0.0.1",
        ui_port=DEFAULT_PANEL_PORT,
        install_root=install_root,
        access_mode=access_mode,
    )
    opencode_launcher_path: Path | None
    try:
        opencode_launcher_path = prepare_opencode_launcher(config=config)
    except FileNotFoundError:
        opencode_launcher_path = None

    start_menu_dir = _resolve_start_menu_programs_dir()
    desktop_dir = _resolve_desktop_dir()
    start_menu_dir.mkdir(parents=True, exist_ok=True)
    desktop_dir.mkdir(parents=True, exist_ok=True)
    _remove_legacy_windows_shortcuts(start_menu_dir=start_menu_dir, desktop_dir=desktop_dir)

    legacy_hidden_launcher_path = panel_root / "Open-RuntimePilot.vbs"
    if legacy_hidden_launcher_path.exists():
        legacy_hidden_launcher_path.unlink(missing_ok=True)
    _write_windows_legacy_panel_compat_launchers(
        panel_root=panel_root,
        panel_launcher_path=panel_launcher_path,
    )
    panel_startup_splash_path = panel_root / WINDOWS_PANEL_STARTUP_SPLASH_NAME
    panel_shortcut_target = startup_shortcut_target
    panel_shortcut_arguments = startup_shortcut_arguments
    if panel_shortcut_target is None:
        _write_windows_panel_startup_splash(
            startup_splash_path=panel_startup_splash_path,
            panel_url=DEFAULT_PANEL_URL,
            expected_install_root=install_root,
            panel_launcher_path=panel_launcher_path,
        )
        panel_shortcut_target = panel_startup_splash_path
        panel_shortcut_arguments = ""
        mshta_path = _resolve_mshta_path()
        if mshta_path is not None:
            panel_shortcut_target = mshta_path
            panel_shortcut_arguments = f'"{panel_startup_splash_path}"'
    else:
        panel_startup_splash_path.unlink(missing_ok=True)
    panel_shortcut_icon = _install_windows_shell_icon(
        panel_root=panel_root,
        resource_path=WINDOWS_PANEL_ICON_RESOURCE,
        installed_name=WINDOWS_PANEL_ICON_NAME,
        fallback_icon_path=panel_executable_path if panel_executable_path.is_file() else None,
    )
    start_menu_panel_shortcut_path = start_menu_dir / PANEL_SHORTCUT_NAME
    _create_windows_shortcut(
        start_menu_panel_shortcut_path,
        panel_shortcut_target,
        working_directory=panel_root,
        description="Open the RuntimePilot panel.",
        arguments=panel_shortcut_arguments,
        icon_path=panel_shortcut_icon,
    )

    desktop_panel_shortcut_path = desktop_dir / PANEL_SHORTCUT_NAME
    _create_windows_shortcut(
        desktop_panel_shortcut_path,
        panel_shortcut_target,
        working_directory=panel_root,
        description="Open the RuntimePilot panel.",
        arguments=panel_shortcut_arguments,
        icon_path=panel_shortcut_icon,
    )

    start_menu_opencode_shortcut_path: Path | None = None
    desktop_opencode_shortcut_path: Path | None = None
    if opencode_launcher_path is not None:
        opencode_shortcut_icon = _install_windows_shell_icon(
            panel_root=panel_root,
            resource_path=WINDOWS_OPENCODE_ICON_RESOURCE,
            installed_name=WINDOWS_OPENCODE_ICON_NAME,
            fallback_icon_path=panel_shortcut_icon,
        )
        start_menu_opencode_shortcut_path = start_menu_dir / OPENCODE_SHORTCUT_NAME
        _create_windows_shortcut(
            start_menu_opencode_shortcut_path,
            opencode_launcher_path,
            working_directory=panel_root,
            description="Open the installer-managed OpenCode console.",
            icon_path=opencode_shortcut_icon,
        )

        desktop_opencode_shortcut_path = desktop_dir / OPENCODE_SHORTCUT_NAME
        _create_windows_shortcut(
            desktop_opencode_shortcut_path,
            opencode_launcher_path,
            working_directory=panel_root,
            description="Open the installer-managed OpenCode console.",
            icon_path=opencode_shortcut_icon,
        )

    uninstall_launcher_path = panel_root / UNINSTALL_LAUNCHER_NAME
    _write_uninstall_launcher(
        uninstall_launcher_path=uninstall_launcher_path,
        panel_executable_path=panel_executable_path,
        install_root=install_root,
    )

    start_menu_uninstall_shortcut_path = start_menu_dir / UNINSTALL_SHORTCUT_NAME
    _create_windows_shortcut(
        start_menu_uninstall_shortcut_path,
        uninstall_launcher_path,
        working_directory=panel_root,
        description="Uninstall RuntimePilot.",
        icon_path=panel_shortcut_icon,
    )

    _register_uninstall_entry(
        install_root=install_root,
        display_icon_path=panel_shortcut_icon or panel_executable_path,
        uninstall_command_path=uninstall_launcher_path,
        display_version=display_version,
    )

    return {
        "opencode_launcher_path": opencode_launcher_path,
        "uninstall_launcher_path": uninstall_launcher_path,
        "start_menu_dir": start_menu_dir,
        "start_menu_panel_shortcut_path": start_menu_panel_shortcut_path,
        "start_menu_opencode_shortcut_path": start_menu_opencode_shortcut_path,
        "start_menu_uninstall_shortcut_path": start_menu_uninstall_shortcut_path,
        "desktop_panel_shortcut_path": desktop_panel_shortcut_path,
        "desktop_opencode_shortcut_path": desktop_opencode_shortcut_path,
        "uninstall_registry_key": UNINSTALL_REGISTRY_KEY,
    }


def _write_windows_legacy_panel_compat_launchers(
    *,
    panel_root: Path,
    panel_launcher_path: Path,
) -> None:
    legacy_cmd_path = panel_root / "Open-Control-Center.cmd"
    legacy_vbs_path = panel_root / "Open-Control-Center.vbs"

    legacy_cmd_lines = [
        "@echo off",
        "setlocal",
        'call "%~dp0Open-RuntimePilot.cmd" %*',
        "endlocal",
    ]
    legacy_cmd_path.write_text("\r\n".join(legacy_cmd_lines) + "\r\n", encoding="utf-8")

    legacy_vbs_lines = [
        'Set shell = CreateObject("WScript.Shell")',
        'Set fso = CreateObject("Scripting.FileSystemObject")',
        'launcher = fso.BuildPath(fso.GetParentFolderName(WScript.ScriptFullName), "Open-RuntimePilot.cmd")',
        'shell.Run "cmd.exe /d /c """" & launcher & """"", 0, False',
    ]
    legacy_vbs_path.write_text("\r\n".join(legacy_vbs_lines) + "\r\n", encoding="utf-8")


def _write_uninstall_launcher(
    *,
    uninstall_launcher_path: Path,
    panel_executable_path: Path,
    install_root: Path,
) -> None:
    uninstall_launcher_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "@echo off",
        "setlocal",
        f"echo RuntimePilot uninstall je pokrenut.",
        f'"{panel_executable_path}" --uninstall --install-root "{install_root}"',
        'set "LACC_UNINSTALL_EXIT_CODE=%ERRORLEVEL%"',
        'if not "%LACC_UNINSTALL_EXIT_CODE%"=="0" (',
        "  echo.",
        "  echo Deinstalacija nije završena uspešno.",
        "  pause",
        ")",
        "endlocal",
    ]
    uninstall_launcher_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")


def _write_windows_panel_startup_splash(
    *,
    startup_splash_path: Path,
    panel_url: str,
    expected_install_root: Path,
    panel_launcher_path: Path,
) -> None:
    startup_splash_path.parent.mkdir(parents=True, exist_ok=True)
    health_url = f"{panel_url.rstrip('/')}/health"
    browser_open_marker_path = startup_splash_path.parent / ".runtimepilot-browser-opened.flag"
    panel_url_js = json.dumps(panel_url)
    health_url_js = json.dumps(health_url)
    install_root_js = json.dumps(str(expected_install_root.resolve()))
    launcher_command_js = json.dumps(f'cmd.exe /d /c "{str(panel_launcher_path)}"')
    browser_watcher_command_js = json.dumps(
        _build_windows_browser_watcher_command(
            panel_url=panel_url,
            expected_install_root=expected_install_root,
            marker_path=browser_open_marker_path,
        )
    )
    browser_open_marker_path_js = json.dumps(str(browser_open_marker_path.resolve()))
    logo_source_js = json.dumps(WINDOWS_PANEL_ICON_NAME)
    html = f"""<!DOCTYPE html>
<html lang="sr">
<head>
  <meta charset="utf-8" />
  <title>RuntimePilot startup</title>
  <HTA:APPLICATION
    APPLICATIONNAME="RuntimePilot Startup"
    BORDER="thin"
    CAPTION="yes"
    SHOWINTASKBAR="yes"
    SINGLEINSTANCE="yes"
    SYSMENU="yes"
    SCROLL="no"
    RESIZE="no"
    WINDOWSTATE="normal"
  />
  <style>
    html {{
      background: #14110d;
    }}
    body {{
      margin: 0;
      padding: 18px;
      background: #14110d;
      color: #f4efe6;
      font-family: Segoe UI, Arial, sans-serif;
    }}
    .shell {{
      margin: 0;
      border: 1px solid #7f6a47;
      background: #231e19;
      padding: 28px 32px 24px;
    }}
    .hero {{
      overflow: hidden;
    }}
    .logo-frame {{
      float: left;
      width: 110px;
      height: 110px;
      margin-right: 24px;
      border: 1px solid #7f6a47;
      background: #15110d;
      text-align: center;
    }}
    .logo-img {{
      width: 74px;
      height: 74px;
      margin-top: 18px;
      border: 0;
    }}
    .hero-copy {{
      overflow: hidden;
    }}
    .brand {{
      font-size: 13px;
      letter-spacing: 0.22em;
      text-transform: uppercase;
      color: #cbb089;
      margin-bottom: 10px;
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 32px;
      line-height: 1.08;
      color: #fff9ee;
    }}
    p {{
      margin: 0;
      color: #ddd3c5;
      line-height: 1.6;
      font-size: 16px;
    }}
    .status-box {{
      margin-top: 20px;
      border: 1px solid #5d4d34;
      background: #1a1713;
      padding: 18px 20px 16px;
    }}
    .status-title {{
      font-size: 19px;
      font-weight: 700;
      margin-bottom: 8px;
      color: #fff8ec;
    }}
    .status-detail {{
      min-height: 50px;
      font-size: 16px;
      line-height: 1.55;
      color: #ded4c6;
    }}
    .meter {{
      margin-top: 18px;
      height: 9px;
      border: 1px solid #69573a;
      background: #2a241d;
      overflow: hidden;
    }}
    .meter-fill {{
      width: 32%;
      height: 100%;
      background: #d9c29a;
      animation: scan 1.1s ease-in-out infinite alternate;
    }}
    .meta {{
      margin-top: 18px;
      font-size: 15px;
      color: #ded4c6;
    }}
    .meta-row {{
      margin-top: 8px;
    }}
    .meta strong {{
      display: inline-block;
      width: 80px;
      color: #fff8ec;
      font-weight: 700;
    }}
    .meta-link {{
      color: #f7efe2;
      text-decoration: underline;
      background: #3a3128;
      border: 1px solid #6b593d;
      padding: 6px 8px;
      display: inline-block;
      word-break: break-all;
    }}
    .meta-link:hover {{
      background: #4a3e31;
      border-color: #85704e;
      color: #fffaf2;
    }}
    .action-bar {{
      margin-top: 18px;
    }}
    .action-button {{
      margin: 0 10px 10px 0;
      padding: 8px 12px;
      border: 1px solid #7a6645;
      background: #332a22;
      color: #f5eee2;
      font-family: Segoe UI, Arial, sans-serif;
      font-size: 14px;
      cursor: pointer;
    }}
    .action-button:hover {{
      background: #43372c;
      border-color: #99815c;
    }}
    .action-button-primary {{
      background: #c3a36b;
      border-color: #d8bf93;
      color: #17120d;
      font-weight: 700;
    }}
    .action-button-primary:hover {{
      background: #d1b381;
      border-color: #e4cfaa;
    }}
    .notice {{
      margin-top: 20px;
      border: 1px solid #5f5037;
      background: #1d1915;
      padding: 16px 18px;
    }}
    .notice-title {{
      font-size: 12px;
      letter-spacing: 0.11em;
      text-transform: uppercase;
      color: #d5b884;
      font-weight: 700;
      margin-bottom: 8px;
    }}
    .notice p {{
      margin: 8px 0 0;
      font-size: 13px;
      line-height: 1.58;
      color: #ddd4c5;
    }}
    code {{
      color: #f4ecde;
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
      word-break: break-all;
      background: #312920;
      padding: 1px 4px;
    }}
    .hint {{
      margin-top: 18px;
      font-size: 12px;
      color: #bad2a2;
      letter-spacing: 0.09em;
      text-transform: uppercase;
    }}
    @keyframes scan {{
      from {{ transform: translateX(-22%); }}
      to {{ transform: translateX(165%); }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <div class="hero">
      <div class="logo-frame" id="startup-logo-frame">
        <img id="startup-logo" class="logo-img" alt="RuntimePilot logo" src="" />
      </div>
      <div class="hero-copy">
        <div class="brand">RuntimePilot startup</div>
        <h1>Panel se podiže</h1>
        <p>Pokrećem lokalni RuntimePilot i proveravam kada je portal spreman za rad u browseru.</p>
      </div>
    </div>

    <div class="status-box">
      <div id="status-title" class="status-title">Čekam health signal...</div>
      <div id="status-detail" class="status-detail">Backend se podiže i čim potvrdi da je spreman, portal će se otvoriti automatski.</div>
      <div class="meter"><div class="meter-fill"></div></div>
    </div>

    <div class="meta">
      <div class="meta-row"><strong>Portal</strong> <a id="portal-link" class="meta-link" href="#"></a></div>
      <div class="meta-row"><strong>Provera</strong> <a id="health-link" class="meta-link" href="#"></a></div>
      <div class="meta-row"><strong>Stanje</strong> <span id="attempt-label">pokretanje</span></div>
    </div>

    <div class="action-bar">
      <input id="open-portal-button" class="action-button action-button-primary" type="button" value="Otvori portal odmah" onclick="openPortalNow();" />
      <input id="open-folder-button" class="action-button" type="button" value="Otvori RuntimePilot folder" onclick="openInstallFolder();" />
      <input id="copy-path-button" class="action-button" type="button" value="Kopiraj putanju za exception" onclick="copyInstallPath();" />
    </div>

    <div class="notice">
      <div class="notice-title">Ako browser ne iskoci automatski</div>
      <p>Klikni direktno na <strong>Portal</strong> link iznad i RuntimePilot će se otvoriti ručno u podrazumevanom browseru.</p>
      <p>Neki antivirus paketi, posebno <strong>Avast</strong>, umeju pogrešno da prijave ovaj startup tok kao trojanski zato što lokalni <code>RuntimePilot-Startup.hta</code> proverava health i otvara browser preko Windows shell-a.</p>
      <p>Ovaj prozor ne preuzima ništa sa interneta: samo pokreće tvoj lokalni panel u <code id="install-root-path"></code> i proverava da li je spreman.</p>
      <p>Ako veruješ ovoj instalaciji, dodaj exception samo za RuntimePilot folder iznad. Nemoj da praviš globalni exception za ceo antivirus niti za ceo <code>mshta.exe</code>.</p>
    </div>

    <div class="hint">Kada health postane zelen, RuntimePilot otvara tvoj podrazumevani browser.</div>
  </div>

  <script language="javascript">
    var targetUrl = {panel_url_js};
    var healthUrl = {health_url_js};
    var expectedInstallRoot = {install_root_js};
    var launcherCommand = {launcher_command_js};
    var browserWatcherCommand = {browser_watcher_command_js};
    var browserOpenMarkerPath = {browser_open_marker_path_js};
    var logoSource = {logo_source_js};
    var shell = new ActiveXObject("WScript.Shell");
    var appShell = new ActiveXObject("Shell.Application");
    var fileSystem = new ActiveXObject("Scripting.FileSystemObject");
    var attempts = 0;
    var maxSlowAttempts = 8;
    var launchRequested = false;
    var browserOpenRequested = false;
    var browserWatcherStarted = false;

    function byId(id) {{
      return document.getElementById(id);
    }}

    function normalizeInstallRoot(value) {{
      return String(value || "").replace(/\\//g, "\\\\").toLowerCase();
    }}

    function setStatus(title, detail, label) {{
      byId("status-title").innerText = title;
      byId("status-detail").innerText = detail;
      byId("attempt-label").innerText = label;
    }}

    function resetBrowserOpenMarker() {{
      try {{
        if (fileSystem.FileExists(browserOpenMarkerPath)) {{
          fileSystem.DeleteFile(browserOpenMarkerPath, true);
        }}
      }} catch (error) {{
      }}
    }}

    function browserWasOpened() {{
      try {{
        return fileSystem.FileExists(browserOpenMarkerPath);
      }} catch (error) {{
      }}
      return false;
    }}

    function markBrowserOpened(label) {{
      try {{
        var markerFile = fileSystem.CreateTextFile(browserOpenMarkerPath, true);
        markerFile.WriteLine(String(label || "opened"));
        markerFile.Close();
        return true;
      }} catch (error) {{
      }}
      return false;
    }}

    function openExternal(url) {{
      try {{
        appShell.ShellExecute(url, "", "", "open", 1);
        return true;
      }} catch (error) {{
      }}
      try {{
        shell.Run('rundll32.exe url.dll,FileProtocolHandler "' + url + '"', 1, false);
        return true;
      }} catch (error) {{
      }}
      try {{
        shell.Run('cmd.exe /c start "" "' + url + '"', 0, false);
        return true;
      }} catch (error) {{
      }}
      try {{
        shell.Run(url, 1, false);
        return true;
      }} catch (error) {{
      }}
      return false;
    }}

    function openMetaLink(event, url) {{
      if (event) {{
        if (event.preventDefault) {{
          event.preventDefault();
        }}
        event.returnValue = false;
      }}
      openExternal(url);
      return false;
    }}

    function openPortalWithFeedback(title, detail, label, closeDelayMs) {{
      if (openExternal(targetUrl)) {{
        markBrowserOpened(label || "manual");
        setStatus(title, detail, label);
        window.setTimeout(function () {{
          window.close();
        }}, closeDelayMs);
        return true;
      }}
      return false;
    }}

    function openPortalNow() {{
      if (openPortalWithFeedback(
        "Portal se otvara ručno",
        "Ako ga ne vidiš odmah, proveri taskbar ili Alt+Tab. Ovaj startup prozor će se zatvoriti.",
        "ručno otvaranje",
        900
      )) {{
        return true;
      }}
      setStatus(
        "Portal nije mogao da se otvori",
        "Klik na Portal link iznad i dalje ostaje rezervni put ako automatsko otvaranje zakaže.",
        "ručno otvaranje nije uspelo"
      );
      return false;
    }}

    function openInstallFolder() {{
      try {{
        shell.Run('explorer.exe "' + expectedInstallRoot + '"', 1, false);
        setStatus(
          "Otvoren je RuntimePilot folder",
          "Sada možeš direktno da dodaš Avast exception baš za ovu lokaciju.",
          "folder otvoren"
        );
        return true;
      }} catch (error) {{
      }}
      return false;
    }}

    function copyInstallPath() {{
      try {{
        window.clipboardData.setData("Text", expectedInstallRoot);
        setStatus(
          "Putanja je kopirana",
          "Možeš odmah da je nalepiš u Avast exception polje.",
          "putanja kopirana"
        );
        return true;
      }} catch (error) {{
      }}
      setStatus(
        "Kopiranje nije uspelo",
        "Ako clipboard blokira kopiranje, koristi dugme za otvaranje RuntimePilot foldera pa exception dodaj ručno.",
        "kopiranje nije uspelo"
      );
      return false;
    }}

    function hydrateLogo() {{
      if (logoSource) {{
        byId("startup-logo").setAttribute("src", logoSource);
        return;
      }}
      byId("startup-logo-frame").style.display = "none";
    }}

    function ensureBrowserWatcher() {{
      if (browserWatcherStarted) {{
        return;
      }}
      browserWatcherStarted = true;
      try {{
        shell.Run(browserWatcherCommand, 0, false);
      }} catch (error) {{
      }}
    }}

    function markReadyAndOpen() {{
      if (browserOpenRequested) {{
        return;
      }}
      browserOpenRequested = true;
      ensureBrowserWatcher();
      setStatus(
        "Portal se otvara automatski",
        "RuntimePilot je spreman. Tihi launcher sada otvara browser, a ovaj startup prozor će se zatvoriti čim potvrdi otvaranje.",
        "otvaram browser"
      );
    }}

    function ensurePanelLaunch() {{
      if (launchRequested) {{
        return;
      }}
      launchRequested = true;
      try {{
        shell.Run(launcherCommand, 0, false);
      }} catch (error) {{
      }}
      ensureBrowserWatcher();
    }}

    function probeHealth() {{
      if (browserWasOpened()) {{
        setStatus(
          "Browser je otvoren",
          "Portal je otvoren u podrazumevanom browseru. Ovaj startup prozor se sada zatvara.",
          "browser potvrđen"
        );
        window.setTimeout(function () {{
          window.close();
        }}, 2200);
        return;
      }}
      attempts += 1;
      try {{
        var request = new ActiveXObject("WinHttp.WinHttpRequest.5.1");
        request.SetTimeouts(250, 250, 750, 750);
        request.Open("GET", healthUrl + "?cb=" + new Date().getTime(), false);
        request.Send();
        if (request.Status === 200) {{
          var payload = JSON.parse(request.ResponseText);
          if (
            String(payload.status || "").toLowerCase() === "ok" &&
            String(payload.app || "") === "local-ai-control-center-stable" &&
            normalizeInstallRoot(payload.installRoot) === normalizeInstallRoot(expectedInstallRoot)
          ) {{
            markReadyAndOpen();
            return;
          }}
        }}
      }} catch (error) {{
      }}

      if (browserOpenRequested) {{
        setStatus(
          "Portal je spreman",
          "Health je potvrđen. Ako browser još nije iskočio, sačekaj još trenutak ili klikni Portal link iznad.",
          "čekam browser"
        );
        return;
      }}

      if (attempts >= maxSlowAttempts) {{
        setStatus(
          "Pokretanje traje malo duže",
          "RuntimePilot i dalje čeka da lokalni panel vrati zdrav odgovor. Ako je runtime težak, ovo je normalno kratko vreme.",
          "čekam odgovor"
        );
      }} else {{
        setStatus(
          "RuntimePilot se podiže",
          "Panel je startovan, sada čekam health potvrdu da bih otvorio puni portal bez prazne ili zbunjujuće stranice.",
          "proveravam health"
        );
      }}
    }}

    hydrateLogo();
    byId("portal-link").innerText = targetUrl;
    byId("portal-link").setAttribute("href", targetUrl);
    byId("portal-link").onclick = function () {{
      return openMetaLink(window.event, targetUrl);
    }};
    byId("health-link").innerText = healthUrl;
    byId("health-link").setAttribute("href", healthUrl);
    byId("health-link").onclick = function () {{
      return openMetaLink(window.event, healthUrl);
    }};
    byId("install-root-path").innerText = expectedInstallRoot;
    resetBrowserOpenMarker();
    ensurePanelLaunch();
    window.setInterval(probeHealth, 900);
    probeHealth();
  </script>
</body>
</html>
"""
    startup_splash_path.write_text(html, encoding="utf-8")


def _write_linux_uninstall_launcher(
    uninstall_launcher_path: Path,
    *,
    install_root: Path,
) -> None:
    uninstall_launcher_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        f'echo "Linux uninstall launcher jos nije implementiran za: {install_root}"',
        "exit 1",
    ]
    uninstall_launcher_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _ensure_executable_bit(uninstall_launcher_path)


def _resolve_start_menu_programs_dir() -> Path:
    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / START_MENU_FOLDER_NAME


def _remove_legacy_windows_shortcuts(*, start_menu_dir: Path, desktop_dir: Path) -> None:
    legacy_start_menu_dirs = [start_menu_dir.parent / name for name in LEGACY_START_MENU_FOLDER_NAMES]
    for legacy_start_menu_dir in legacy_start_menu_dirs:
        for shortcut_name in (
            *LEGACY_PANEL_SHORTCUT_NAMES,
            OPENCODE_SHORTCUT_NAME,
            *LEGACY_UNINSTALL_SHORTCUT_NAMES,
        ):
            (legacy_start_menu_dir / shortcut_name).unlink(missing_ok=True)
        try:
            legacy_start_menu_dir.rmdir()
        except OSError:
            pass
    for shortcut_name in (*LEGACY_PANEL_SHORTCUT_NAMES, OPENCODE_SHORTCUT_NAME):
        (desktop_dir / shortcut_name).unlink(missing_ok=True)


def _resolve_desktop_dir() -> Path:
    return Path.home() / "Desktop"


def _resolve_mshta_path() -> Path | None:
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    mshta_path = system_root / "System32" / "mshta.exe"
    if mshta_path.is_file():
        return mshta_path
    return None


def _ensure_executable_bit(path: Path) -> None:
    current_mode = path.stat().st_mode
    path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _create_windows_shortcut(
    shortcut_path: Path,
    target_path: Path,
    *,
    working_directory: Path | None = None,
    description: str = "",
    arguments: str = "",
    icon_path: Path | None = None,
) -> None:
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)
    shortcut_path.unlink(missing_ok=True)
    powershell_lines = [
        "$shell = New-Object -ComObject WScript.Shell",
        f"$shortcut = $shell.CreateShortcut({_quote_powershell_string(str(shortcut_path))})",
        f"$shortcut.TargetPath = {_quote_powershell_string(str(target_path))}",
        f"$shortcut.Arguments = {_quote_powershell_string(arguments)}",
    ]
    if working_directory is not None:
        powershell_lines.append(
            f"$shortcut.WorkingDirectory = {_quote_powershell_string(str(working_directory))}"
        )
    if description:
        powershell_lines.append(f"$shortcut.Description = {_quote_powershell_string(description)}")
    if icon_path is not None and icon_path.exists():
        powershell_lines.append(
            f"$shortcut.IconLocation = {_quote_powershell_string(str(icon_path))}"
        )
    powershell_lines.append("$shortcut.Save()")
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            " ; ".join(powershell_lines),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
        raise RuntimeError(f"Windows shortcut nije mogao da se napravi: {detail}")


def _register_uninstall_entry(
    *,
    install_root: Path,
    display_icon_path: Path,
    uninstall_command_path: Path,
    display_version: str,
) -> None:
    entry_values = {
        "DisplayName": "RuntimePilot",
        "DisplayVersion": display_version,
        "Publisher": "joes021",
        "InstallLocation": str(install_root),
        "DisplayIcon": str(display_icon_path),
        "UninstallString": str(uninstall_command_path),
        "QuietUninstallString": str(uninstall_command_path),
        "NoModify": "1",
        "NoRepair": "1",
    }
    for name, value in entry_values.items():
        completed = subprocess.run(
            [
                "reg",
                "add",
                UNINSTALL_REGISTRY_KEY,
                "/v",
                name,
                "/t",
                "REG_SZ",
                "/d",
                value,
                "/f",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
            raise RuntimeError(f"Windows uninstall entry nije mogao da se upise: {detail}")


def _resolve_installer_version() -> str:
    try:
        return package_version("local-ai-control-center-installer")
    except PackageNotFoundError:
        return "unknown"


def _resolve_display_version(source_executable_path: Path) -> str:
    file_name = source_executable_path.name
    marker = "RuntimePilotSetup-v"
    if file_name.lower().startswith(marker.lower()) and file_name.lower().endswith(".exe"):
        return file_name[len(marker) : -4]
    return _resolve_installer_version()


def _quote_windows_part(value: str) -> str:
    if " " in value or "\t" in value:
        return f"\"{value}\""
    return value


def _panel_health_ready(
    url: str,
    *,
    expected_install_root: str | None = None,
) -> bool:
    try:
        with urlopen(f"{url}health", timeout=1.0) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read().decode("utf-8"))
            if payload.get("status") != "ok":
                return False
            if payload.get("app") != "local-ai-control-center-stable":
                return False
            if expected_install_root is not None:
                return payload.get("installRoot") == expected_install_root
            return True
    except URLError:
        return False
    except OSError:
        return False
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return False

def _stop_existing_panel_for_update(
    *,
    install_root: Path,
    port: int,
    panel_executable_path: Path,
    replacement_panel_path: Path | None = None,
    timeout_seconds: float = 10.0,
    platform: str | None = None,
) -> None:
    panel_url = f"http://127.0.0.1:{port}/"
    if not _panel_health_ready(panel_url, expected_install_root=str(install_root)):
        return

    if (
        replacement_panel_path is not None
        and _files_have_same_contents(replacement_panel_path, panel_executable_path)
    ):
        return

    try:
        pids = _find_panel_process_ids(panel_executable_path, platform=platform)
    except TypeError:
        pids = _find_panel_process_ids(panel_executable_path)
    if not pids:
        try:
            listening_pid = _find_listening_pid(port, platform=platform)
        except TypeError:
            listening_pid = _find_listening_pid(port)
        if listening_pid is not None:
            pids = [listening_pid]

    if not pids:
        raise RuntimeError(
            f"RuntimePilot panel je aktivan na portu {port}, ali PID nije mogao da se odredi."
        )

    for pid in pids:
        detail = _stop_process_id(pid, platform=platform)
        if detail is not None:
            if _is_benign_missing_process_stop_error(detail):
                continue
            raise RuntimeError(f"RuntimePilot panel nije mogao da se zaustavi: {detail}")

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not _port_in_use("127.0.0.1", port):
            return
        time.sleep(0.25)

    raise TimeoutError(
        f"RuntimePilot panel nije oslobodio port {port} posle zaustavljanja."
    )


def _resolve_panel_binary_source(
    *,
    panel_executable_resource: Path | None,
    frozen: bool,
    candidate_frozen_executable: Path,
    platform: str | None = None,
) -> Path | None:
    if (
        panel_executable_resource is not None
        and panel_executable_resource.is_file()
        and _is_windows_runtime_platform(platform)
    ):
        return panel_executable_resource.resolve()
    if frozen and candidate_frozen_executable.is_file():
        return candidate_frozen_executable.resolve()
    return None


def _is_benign_missing_process_stop_error(detail: str) -> bool:
    normalized = detail.strip().lower()
    if not normalized:
        return False
    return "not found" in normalized or "no such process" in normalized


def _files_have_same_contents(source: Path, destination: Path) -> bool:
    try:
        source_path = source.resolve()
        destination_path = destination.resolve()
        if source_path == destination_path:
            return True
        if not source_path.is_file() or not destination_path.is_file():
            return False
        if source_path.stat().st_size != destination_path.stat().st_size:
            return False
        with source_path.open("rb") as source_handle, destination_path.open(
            "rb"
        ) as destination_handle:
            while True:
                source_chunk = source_handle.read(1024 * 1024)
                destination_chunk = destination_handle.read(1024 * 1024)
                if source_chunk != destination_chunk:
                    return False
                if not source_chunk:
                    return True
    except OSError:
        return False


def _copy_panel_executable(source: Path, destination: Path) -> None:
    if _files_have_same_contents(source, destination):
        return
    try:
        shutil.copy2(source, destination)
    except PermissionError:
        _wait_for_path_replaceable(destination)
        shutil.copy2(source, destination)
    if destination.suffix.lower() != ".exe":
        _ensure_executable_bit(destination)


def _find_panel_process_ids(executable_path: Path, *, platform: str | None = None) -> list[int]:
    if not _is_windows_runtime_platform(platform):
        result = subprocess.run(
            ["ps", "-eo", "pid=,args="],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            return []
        process_ids: list[int] = []
        target = str(executable_path)
        for raw_line in result.stdout.splitlines():
            line = raw_line.strip()
            if not line or target not in line:
                continue
            parts = line.split(None, 1)
            if not parts:
                continue
            try:
                process_ids.append(int(parts[0]))
            except ValueError:
                continue
        return process_ids

    powershell_command = (
        "$target = "
        + _quote_powershell_string(str(executable_path))
        + "; Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq $target } "
        + "| Select-Object -ExpandProperty ProcessId"
    )
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            powershell_command,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        return []

    process_ids: list[int] = []
    for raw_line in result.stdout.splitlines():
        candidate = raw_line.strip()
        if not candidate:
            continue
        try:
            process_ids.append(int(candidate))
        except ValueError:
            continue
    return process_ids


def _find_listening_pid(port: int, *, platform: str | None = None) -> int | None:
    if not _is_windows_runtime_platform(platform):
        listener_pid = _find_linux_listening_pid_with_ss(port)
        if listener_pid is not None:
            return listener_pid
        return _find_linux_listening_pid_with_lsof(port)

    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        return None

    expected_local_address = f"127.0.0.1:{port}".lower()
    for raw_line in result.stdout.splitlines():
        columns = raw_line.split()
        if len(columns) < 5 or columns[0].upper() != "TCP":
            continue
        local_address = columns[1].lower()
        state = columns[3].upper()
        pid_raw = columns[4]
        if local_address != expected_local_address or state != "LISTENING":
            continue
        try:
            return int(pid_raw)
        except ValueError:
            return None
    return None


def _find_linux_listening_pid_with_ss(port: int) -> int | None:
    result = subprocess.run(
        ["ss", "-ltnp"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return None

    for raw_line in result.stdout.splitlines():
        if f":{port}" not in raw_line:
            continue
        match = re.search(r"pid=(\d+)", raw_line)
        if match:
            return int(match.group(1))
    return None


def _find_linux_listening_pid_with_lsof(port: int) -> int | None:
    if shutil.which("lsof") is None:
        return None
    result = subprocess.run(
        ["lsof", "-tiTCP", str(port), "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return None
    for raw_line in result.stdout.splitlines():
        candidate = raw_line.strip()
        if not candidate:
            continue
        try:
            return int(candidate)
        except ValueError:
            continue
    return None


def _stop_process_id(pid: int, *, platform: str | None = None) -> str | None:
    if not _is_windows_runtime_platform(platform):
        completed = subprocess.run(
            ["kill", str(pid)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode == 0:
            return None
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
        return detail

    completed = subprocess.run(
        ["taskkill", "/PID", str(pid), "/F"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=hidden_subprocess_creationflags(),
    )
    if completed.returncode == 0:
        return None
    return completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def _wait_for_path_replaceable(path: Path, timeout_seconds: float = 10.0) -> None:
    if not path.exists():
        return

    deadline = time.monotonic() + timeout_seconds
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            with path.open("ab"):
                return
        except OSError as exc:
            last_error = exc
            time.sleep(0.25)

    if last_error is not None:
        raise last_error
    raise TimeoutError(f"Path did not become replaceable in time: {path}")


def _wait_for_port_release(host: str, port: int, timeout_seconds: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not _port_in_use(host, port):
            return
        time.sleep(0.25)
    raise TimeoutError(f"RuntimePilot panel nije oslobodio port {port} u ocekivanom roku.")


def _quote_powershell_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
