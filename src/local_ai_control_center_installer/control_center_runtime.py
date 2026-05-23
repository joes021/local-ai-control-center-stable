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
    OPENCODE_SHORTCUT_NAME,
    PANEL_SHORTCUT_NAME,
    START_MENU_FOLDER_NAME,
    UNINSTALL_REGISTRY_KEY,
    UNINSTALL_SHORTCUT_NAME,
)
from local_ai_control_center_installer.session import InstallerSession


PANEL_EXECUTABLE_NAME = "LocalAIControlCenterPanel.exe"
UNINSTALL_LAUNCHER_NAME = "Uninstall-LocalAIControlCenter.cmd"
DEFAULT_PANEL_PORT = 3210
DEFAULT_PANEL_URL = f"http://127.0.0.1:{DEFAULT_PANEL_PORT}/"


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


def deploy_control_center_runtime(
    install_root: str | Path,
    *,
    panel_executable_resource: Path | None = None,
    current_python: str | None = None,
    frozen: bool | None = None,
    frozen_executable: str | Path | None = None,
) -> ControlCenterRuntimeDeployment:
    normalized_install_root = Path(install_root).expanduser().resolve()
    panel_root = normalized_install_root / "control-center"
    panel_root.mkdir(parents=True, exist_ok=True)
    launcher_path = panel_root / "Open-Control-Center.cmd"
    _stop_existing_panel_for_update(
        install_root=normalized_install_root,
        port=DEFAULT_PANEL_PORT,
        panel_executable_path=panel_root / PANEL_EXECUTABLE_NAME,
    )

    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))

    panel_executable_resource = panel_executable_resource or _resolve_panel_executable_resource()
    if panel_executable_resource is not None and panel_executable_resource.is_file():
        executable_path = panel_root / PANEL_EXECUTABLE_NAME
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
            "--open-browser",
        )
        _write_launcher_script(
            launcher_path,
            command,
            env_overrides=None,
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

    candidate_frozen_executable = (
        Path(frozen_executable).expanduser().resolve()
        if frozen_executable is not None
        else Path(sys.executable).resolve()
    )
    if frozen and candidate_frozen_executable.is_file():
        executable_path = panel_root / PANEL_EXECUTABLE_NAME
        _copy_panel_executable(candidate_frozen_executable, executable_path)
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
            "--open-browser",
        )
        _write_launcher_script(
            launcher_path,
            command,
            env_overrides=None,
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
        "--open-browser",
    )
    launcher_path.write_text(
        "@echo off\r\n"
        f"set \"LACC_INSTALL_ROOT={normalized_install_root}\"\r\n"
        f"set \"LACC_UI_PORT={DEFAULT_PANEL_PORT}\"\r\n"
        f"set \"LACC_UI_ACCESS_MODE=local-only\"\r\n"
        f"set \"PYTHONPATH={src_root}\"\r\n"
        f"start \"\" \"{python_executable}\" -m local_ai_control_center_installer.control_center_panel "
        f"--install-root \"{normalized_install_root}\" --host 127.0.0.1 --port {DEFAULT_PANEL_PORT} "
        "--access-mode local-only --open-browser\r\n",
        encoding="utf-8",
    )
    shell_assets = _ensure_windows_shell_assets(
        install_root=normalized_install_root,
        panel_root=panel_root,
        panel_launcher_path=launcher_path,
        panel_executable_path=Path(python_executable),
        access_mode="local-only",
        display_version=_resolve_display_version(Path(python_executable)),
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
        _open_panel_url(deployment.url)
        return deployment

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
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
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

    raise TimeoutError("Control Center panel nije odgovorio na /health u predvidjenom roku.")


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


def _write_launcher_script(
    launcher_path: Path,
    command: tuple[str, ...],
    *,
    env_overrides: dict[str, str] | None,
) -> None:
    launcher_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["@echo off"]
    for key, value in (env_overrides or {}).items():
        lines.append(f"set \"{key}={value}\"")
    quoted_command = " ".join(_quote_windows_part(part) for part in command)
    lines.append(f"start \"\" {quoted_command}")
    launcher_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")


def _ensure_windows_shell_assets(
    *,
    install_root: Path,
    panel_root: Path,
    panel_launcher_path: Path,
    panel_executable_path: Path,
    access_mode: str,
    display_version: str,
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

    panel_shortcut_target = panel_launcher_path
    panel_shortcut_icon = panel_executable_path if panel_executable_path.is_file() else None
    start_menu_panel_shortcut_path = start_menu_dir / PANEL_SHORTCUT_NAME
    _create_windows_shortcut(
        start_menu_panel_shortcut_path,
        panel_shortcut_target,
        working_directory=panel_root,
        description="Open the Local AI Control Center panel.",
        icon_path=panel_shortcut_icon,
    )

    desktop_panel_shortcut_path = desktop_dir / PANEL_SHORTCUT_NAME
    _create_windows_shortcut(
        desktop_panel_shortcut_path,
        panel_shortcut_target,
        working_directory=panel_root,
        description="Open the Local AI Control Center panel.",
        icon_path=panel_shortcut_icon,
    )

    start_menu_opencode_shortcut_path: Path | None = None
    desktop_opencode_shortcut_path: Path | None = None
    if opencode_launcher_path is not None:
        start_menu_opencode_shortcut_path = start_menu_dir / OPENCODE_SHORTCUT_NAME
        _create_windows_shortcut(
            start_menu_opencode_shortcut_path,
            opencode_launcher_path,
            working_directory=panel_root,
            description="Open the installer-managed OpenCode console.",
            icon_path=panel_shortcut_icon,
        )

        desktop_opencode_shortcut_path = desktop_dir / OPENCODE_SHORTCUT_NAME
        _create_windows_shortcut(
            desktop_opencode_shortcut_path,
            opencode_launcher_path,
            working_directory=panel_root,
            description="Open the installer-managed OpenCode console.",
            icon_path=panel_shortcut_icon,
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
        description="Uninstall Local AI Control Center.",
        icon_path=panel_shortcut_icon,
    )

    _register_uninstall_entry(
        install_root=install_root,
        display_icon_path=panel_executable_path,
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
        f"echo Local AI Control Center uninstall je pokrenut.",
        f'"{panel_executable_path}" --uninstall --install-root "{install_root}"',
        'set "LACC_UNINSTALL_EXIT_CODE=%ERRORLEVEL%"',
        'if not "%LACC_UNINSTALL_EXIT_CODE%"=="0" (',
        "  echo.",
        "  echo Deinstalacija nije zavrsena uspesno.",
        "  pause",
        ")",
        "endlocal",
    ]
    uninstall_launcher_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")


def _resolve_start_menu_programs_dir() -> Path:
    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / START_MENU_FOLDER_NAME


def _resolve_desktop_dir() -> Path:
    return Path.home() / "Desktop"


def _create_windows_shortcut(
    shortcut_path: Path,
    target_path: Path,
    *,
    working_directory: Path | None = None,
    description: str = "",
    icon_path: Path | None = None,
) -> None:
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)
    powershell_lines = [
        "$shell = New-Object -ComObject WScript.Shell",
        f"$shortcut = $shell.CreateShortcut({_quote_powershell_string(str(shortcut_path))})",
        f"$shortcut.TargetPath = {_quote_powershell_string(str(target_path))}",
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
        "DisplayName": "Local AI Control Center",
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
    marker = "LocalAIControlCenterSetup-v"
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


def _open_panel_url(url: str) -> None:
    subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f"Start-Process '{url}'",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=False,
    )


def _stop_existing_panel_for_update(
    *,
    install_root: Path,
    port: int,
    panel_executable_path: Path,
    timeout_seconds: float = 10.0,
) -> None:
    panel_url = f"http://127.0.0.1:{port}/"
    if not _panel_health_ready(panel_url, expected_install_root=str(install_root)):
        return

    pids = _find_panel_process_ids(panel_executable_path)
    if not pids:
        listening_pid = _find_listening_pid(port)
        if listening_pid is not None:
            pids = [listening_pid]

    if not pids:
        raise RuntimeError(
            f"Control Center panel je aktivan na portu {port}, ali PID nije mogao da se odredi."
        )

    for pid in pids:
        completed = subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
            raise RuntimeError(f"Control Center panel nije mogao da se zaustavi: {detail}")

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not _port_in_use("127.0.0.1", port):
            return
        time.sleep(0.25)

    raise TimeoutError(
        f"Control Center panel nije oslobodio port {port} posle zaustavljanja."
    )


def _copy_panel_executable(source: Path, destination: Path) -> None:
    try:
        shutil.copy2(source, destination)
    except PermissionError:
        _wait_for_path_replaceable(destination)
        shutil.copy2(source, destination)


def _find_panel_process_ids(executable_path: Path) -> list[int]:
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


def _find_listening_pid(port: int) -> int | None:
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


def _quote_powershell_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
