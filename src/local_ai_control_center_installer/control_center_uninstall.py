from __future__ import annotations

from argparse import ArgumentParser
import os
from pathlib import Path
import subprocess
import tempfile

from local_ai_control_center_installer.platform_paths import is_windows_platform


UNINSTALL_REGISTRY_KEY = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\LocalAIControlCenter"
START_MENU_FOLDER_NAME = "RuntimePilot"
PANEL_SHORTCUT_NAME = "RuntimePilot.lnk"
OPENCODE_SHORTCUT_NAME = "OpenCode.lnk"
UNINSTALL_SHORTCUT_NAME = "Uninstall RuntimePilot.lnk"
LEGACY_START_MENU_FOLDER_NAMES = ("Local AI Control Center",)
LEGACY_PANEL_SHORTCUT_NAMES = ("Local AI Control Center.lnk",)
LEGACY_UNINSTALL_SHORTCUT_NAMES = ("Uninstall Local AI Control Center.lnk",)


def run_control_center_uninstall_entry(
    argv: list[str] | None = None,
    *,
    output_fn=print,
) -> int:
    if not is_windows_platform():
        output_fn("Linux uninstall launcher još nije implementiran.")
        return 1

    parser = ArgumentParser(prog="LocalAIControlCenterPanel.exe --uninstall")
    parser.add_argument("--install-root", required=True)
    args = parser.parse_args(argv)

    install_root = Path(args.install_root).expanduser().resolve()
    if not install_root.exists():
        output_fn(f"Install root nije pronađen: {install_root}")
        return 1

    start_menu_dir = _resolve_start_menu_programs_dir()
    desktop_dir = _resolve_desktop_dir()
    _stop_managed_processes(install_root, current_pid=os.getpid())

    for path in _collect_shortcut_paths(start_menu_dir, desktop_dir):
        _remove_file_if_exists(path)
    _remove_directory_if_empty(start_menu_dir)
    _unregister_uninstall_entry()

    cleanup_script = _write_cleanup_script(
        install_root=install_root,
        start_menu_dir=start_menu_dir,
    )
    _launch_cleanup_script(cleanup_script)

    output_fn("RuntimePilot uninstall je pokrenut.")
    output_fn(f"Install root: {install_root}")
    output_fn("Folder i preostale ikone će biti uklonjeni za nekoliko sekundi.")
    return 0


def _resolve_start_menu_programs_dir() -> Path:
    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / START_MENU_FOLDER_NAME


def _resolve_desktop_dir() -> Path:
    return Path.home() / "Desktop"


def _collect_shortcut_paths(start_menu_dir: Path, desktop_dir: Path) -> list[Path]:
    paths = [
        start_menu_dir / PANEL_SHORTCUT_NAME,
        start_menu_dir / OPENCODE_SHORTCUT_NAME,
        start_menu_dir / UNINSTALL_SHORTCUT_NAME,
        desktop_dir / PANEL_SHORTCUT_NAME,
        desktop_dir / OPENCODE_SHORTCUT_NAME,
    ]
    for legacy_folder_name in LEGACY_START_MENU_FOLDER_NAMES:
        legacy_start_menu_dir = start_menu_dir.parent / legacy_folder_name
        paths.extend(
            [
                legacy_start_menu_dir / legacy_name
                for legacy_name in (
                    *LEGACY_PANEL_SHORTCUT_NAMES,
                    OPENCODE_SHORTCUT_NAME,
                    *LEGACY_UNINSTALL_SHORTCUT_NAMES,
                )
            ]
        )
        paths.extend(
            [
                desktop_dir / legacy_name
                for legacy_name in (*LEGACY_PANEL_SHORTCUT_NAMES, OPENCODE_SHORTCUT_NAME)
            ]
        )
    return paths


def _stop_managed_processes(install_root: Path, *, current_pid: int) -> None:
    panel_root = install_root / "control-center"
    runtime_root = install_root / "runtime" / "llama.cpp"
    opencode_root = install_root / "tools" / "opencode"
    turboquant_root = install_root / "tools" / "turboquant"
    executable_targets = [
        panel_root / "LocalAIControlCenterPanel.exe",
        runtime_root / "llama-server.exe",
        opencode_root / "opencode.exe",
    ]
    executable_targets.extend(turboquant_root.glob("**/llama-server.exe"))
    target_list = ", ".join(_quote_powershell_string(str(path)) for path in executable_targets)
    install_root_raw = _quote_powershell_string(str(panel_root))
    powershell_command = (
        f"$targets = @({target_list}); "
        f"$panelRoot = {install_root_raw}; "
        "Get-CimInstance Win32_Process | Where-Object { "
        f"$_.ProcessId -ne {current_pid} -and ("
        "($_.ExecutablePath -and $targets -contains $_.ExecutablePath) -or "
        "($_.Name -eq 'cmd.exe' -and $_.CommandLine -like ('*' + $panelRoot + '*'))"
        ") } | ForEach-Object { "
        "Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue "
        "}"
    )
    subprocess.run(
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


def _remove_file_if_exists(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return


def _remove_directory_if_empty(path: Path) -> None:
    try:
        path.rmdir()
    except OSError:
        return


def _unregister_uninstall_entry() -> None:
    subprocess.run(
        ["reg", "delete", UNINSTALL_REGISTRY_KEY, "/f"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _write_cleanup_script(
    *,
    install_root: Path,
    start_menu_dir: Path,
) -> Path:
    legacy_dirs = [start_menu_dir.parent / name for name in LEGACY_START_MENU_FOLDER_NAMES]
    cleanup_path = Path(tempfile.gettempdir()) / f"lacc-uninstall-{os.getpid()}.cmd"
    cleanup_lines = [
        "@echo off",
        f'set "LACC_INSTALL_ROOT={install_root}"',
        f'set "LACC_START_MENU_DIR={start_menu_dir}"',
        *(
            f'set "LACC_LEGACY_START_MENU_DIR_{index}={legacy_dir}"'
            for index, legacy_dir in enumerate(legacy_dirs, start=1)
        ),
        "ping 127.0.0.1 -n 4 >nul",
        ":retry",
        'rmdir /s /q "%LACC_INSTALL_ROOT%" >nul 2>&1',
        'if exist "%LACC_INSTALL_ROOT%" (',
        "  ping 127.0.0.1 -n 2 >nul",
        "  goto retry",
        ")",
        'rmdir /s /q "%LACC_START_MENU_DIR%" >nul 2>&1',
        *(
            f'rmdir /s /q "%LACC_LEGACY_START_MENU_DIR_{index}%" >nul 2>&1'
            for index, _ in enumerate(legacy_dirs, start=1)
        ),
        'del "%~f0" >nul 2>&1',
    ]
    cleanup_path.write_text("\r\n".join(cleanup_lines) + "\r\n", encoding="utf-8")
    return cleanup_path


def _launch_cleanup_script(cleanup_script: Path) -> None:
    subprocess.Popen(
        [
            "cmd.exe",
            "/c",
            "start",
            "",
            "cmd.exe",
            "/c",
            str(cleanup_script),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=False,
    )


def _quote_powershell_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
