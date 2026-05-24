from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import shlex

from local_ai_control_center_installer.control_center_backend.config import (
    ControlCenterConfig,
    get_config,
)
from local_ai_control_center_installer.control_center_backend.services.server_service import (
    ensure_runtime_ready,
)
from local_ai_control_center_installer.control_center_backend.services.settings_service import (
    apply_opencode_settings,
    delete_opencode_step_preset,
    load_effective_settings_state,
    load_opencode_step_schema,
    save_opencode_step_preset,
)
from local_ai_control_center_installer.control_center_backend.services.status_service import (
    load_runtime_state,
)
from local_ai_control_center_installer.opencode_bootstrap import load_opencode_manifest
from local_ai_control_center_installer.platform_paths import (
    is_windows_platform,
    new_console_subprocess_creationflags,
)


def load_opencode_status_payload(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    executable_path = _resolve_opencode_executable_path(config)
    config_path = config.install_root / "config" / "opencode" / "managed-config.json"
    instances = detect_opencode_instances(executable_path)
    settings = load_effective_settings_state(config)
    runtime_state = load_runtime_state(config)
    runtime_connected = str(runtime_state.get("runtime_live_status", "")) == "started"
    session_state, session_summary = _build_session_state(
        has_instances=bool(instances),
        runtime_connected=runtime_connected,
        runtime_reason=str(runtime_state.get("runtime_live_reason", "") or ""),
    )
    can_open = executable_path.is_file() and config_path.is_file()
    open_action_label, open_blocked_reason = _build_open_action_contract(
        available=executable_path.is_file(),
        config_exists=config_path.is_file(),
        session_state=session_state,
    )

    return {
        "available": executable_path.is_file(),
        "active": bool(instances),
        "instanceCount": len(instances),
        "instances": instances,
        "runtimeConnected": runtime_connected,
        "runtimeLiveStatus": str(runtime_state.get("runtime_live_status", "") or ""),
        "runtimeLiveReason": str(runtime_state.get("runtime_live_reason", "") or ""),
        "sessionState": session_state,
        "sessionSummary": session_summary,
        "canOpen": can_open,
        "openActionLabel": open_action_label,
        "openBlockedReason": open_blocked_reason,
        "configExists": config_path.is_file(),
        "configPath": str(config_path),
        "configDir": str(config_path.parent),
        "executablePath": str(executable_path),
        "workingDirectory": str(settings["workingDirectory"]),
        "buildSteps": int(settings["buildSteps"]),
        "planSteps": int(settings["planSteps"]),
        "generalSteps": int(settings["generalSteps"]),
        "exploreSteps": int(settings["exploreSteps"]),
        "securityMode": str(settings["securityMode"]),
        "securityModeLabel": _security_mode_label(str(settings["securityMode"])),
        "capabilityMode": str(settings["capabilityMode"]),
        "capabilityModeLabel": _capability_mode_label(str(settings["capabilityMode"])),
        "profile": str(settings["profile"]),
        "auditRiskLevel": "",
        "auditSummary": (
            "Installer-managed OpenCode bootstrap je spreman."
            if executable_path.is_file()
            else "OpenCode nije instaliran."
        ),
    }


def open_opencode(
    profile: str = "",
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    executable_path = _resolve_opencode_executable_path(config)
    managed_config_path = config.install_root / "config" / "opencode" / "managed-config.json"
    if not executable_path.is_file():
        return _result("error", "open-opencode", "OpenCode executable nije pronadjen.")
    if not managed_config_path.is_file():
        return _result("error", "open-opencode", "OpenCode managed config nije pronadjen.")
    runtime_result = ensure_runtime_ready(config)
    if runtime_result.get("status") != "ok":
        summary = str(runtime_result.get("summary", "") or "Runtime nije spreman za OpenCode.")
        return _result(
            "error",
            "open-opencode",
            f"OpenCode nije pokrenut. {summary}",
        )
    existing_instances = detect_opencode_instances(executable_path)
    if existing_instances:
        return _result(
            "ok",
            "open-opencode",
            "OpenCode je vec otvoren; backend je pripremljen za postojecu sesiju.",
        )

    log_path = config.install_root / "logs" / "opencode-launch.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    launcher_path = prepare_opencode_launcher(config=config, profile=profile)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"Launching OpenCode via {launcher_path}\n")
    try:
        _launch_opencode_launcher(launcher_path)
    except RuntimeError as exc:
        return _result("error", "open-opencode", str(exc))

    return _result("ok", "open-opencode", "OpenCode je pokrenut u novom prozoru.")


def prepare_opencode_launcher(
    config: ControlCenterConfig | None = None,
    profile: str = "",
    platform: str | None = None,
) -> Path:
    config = config or get_config()
    executable_path = _resolve_opencode_executable_path(config)
    managed_config_path = config.install_root / "config" / "opencode" / "managed-config.json"
    settings = load_effective_settings_state(config)
    if not executable_path.is_file():
        raise FileNotFoundError(f"OpenCode executable nije pronadjen: {executable_path}")
    if not managed_config_path.is_file():
        raise FileNotFoundError(
            f"OpenCode managed config nije pronadjen: {managed_config_path}"
        )

    env = _build_opencode_launch_environment(
        managed_config_path=managed_config_path,
        settings=settings,
        profile=profile,
    )
    launcher_name = "Open-OpenCode.cmd" if is_windows_platform(platform) else "Open-OpenCode.sh"
    launcher_path = config.install_root / "control-center" / launcher_name
    launcher_path.parent.mkdir(parents=True, exist_ok=True)
    _write_opencode_launcher(
        launcher_path=launcher_path,
        executable_path=executable_path,
        working_directory=Path(str(settings["workingDirectory"])),
        env=env,
        platform=platform,
    )
    return launcher_path


def detect_opencode_instances(executable_path: Path) -> list[dict[str, object]]:
    if not executable_path:
        return []
    executable_token = _normalize_windows_path_token(str(executable_path))
    if not executable_token:
        return []
    payloads = _query_opencode_processes()
    if not payloads:
        return []
    instances: list[dict[str, object]] = []
    for item in payloads:
        if not isinstance(item, dict):
            continue
        pid = item.get("pid") or item.get("ProcessId")
        if not isinstance(pid, int):
            continue
        command_line = str(item.get("commandLine") or item.get("CommandLine") or "")
        if not _command_line_matches_executable(command_line, executable_token):
            continue
        instances.append(
            {
                "pid": pid,
                "name": str(item.get("name") or item.get("Name") or ""),
                "commandLine": command_line,
            }
        )
    return instances


def _query_opencode_processes() -> list[dict[str, object]]:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            (
                "$matches = Get-CimInstance Win32_Process "
                "-Filter \"Name = 'opencode.exe'\" "
                "| Select-Object ProcessId, Name, CommandLine; "
                "$matches | ConvertTo-Json -Compress -Depth 3"
            ),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return []
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else [parsed]


def _normalize_windows_path_token(value: str) -> str:
    return value.replace("/", "\\").strip().strip('"').lower()


def _command_line_matches_executable(command_line: str, executable_token: str) -> bool:
    if not command_line or not executable_token:
        return False
    normalized_command = _normalize_windows_path_token(command_line)
    return executable_token in normalized_command


def _resolve_opencode_executable_path(config: ControlCenterConfig) -> Path:
    manifest = load_opencode_manifest()
    artifact = manifest["opencode_artifact"]
    launch = artifact["launch"]["executable_relative_path"]
    return config.install_root / artifact["install_subdir"] / launch


def _build_opencode_launch_environment(
    *,
    managed_config_path: Path,
    settings: dict[str, object],
    profile: str,
) -> dict[str, str]:
    env = os.environ.copy()
    env["OPENCODE_CONFIG"] = str(managed_config_path)
    env["LACC_PROFILE"] = profile or str(settings["profile"])
    env["LACC_OPENCODE_SECURITY_MODE"] = str(settings["securityMode"])
    env["LACC_OPENCODE_CAPABILITY_MODE"] = str(settings["capabilityMode"])
    env["LACC_OPENCODE_BUILD_STEPS"] = str(settings["buildSteps"])
    env["LACC_OPENCODE_PLAN_STEPS"] = str(settings["planSteps"])
    env["LACC_OPENCODE_GENERAL_STEPS"] = str(settings["generalSteps"])
    env["LACC_OPENCODE_EXPLORE_STEPS"] = str(settings["exploreSteps"])
    return env


def _write_opencode_launcher(
    *,
    launcher_path: Path,
    executable_path: Path,
    working_directory: Path,
    env: dict[str, str],
    platform: str | None = None,
) -> None:
    if not is_windows_platform(platform):
        lines = [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            f'cd {shlex.quote(str(working_directory))}',
        ]
        for key in [
            "OPENCODE_CONFIG",
            "LACC_PROFILE",
            "LACC_OPENCODE_SECURITY_MODE",
            "LACC_OPENCODE_CAPABILITY_MODE",
            "LACC_OPENCODE_BUILD_STEPS",
            "LACC_OPENCODE_PLAN_STEPS",
            "LACC_OPENCODE_GENERAL_STEPS",
            "LACC_OPENCODE_EXPLORE_STEPS",
        ]:
            value = str(env.get(key, ""))
            lines.append(f'export {key}="{value}"')
        lines.append(f'exec "{executable_path}" "$@"')
        launcher_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        _ensure_executable_bit(launcher_path)
        return

    lines = [
        "@echo off",
        "setlocal",
        "title Local AI Control Center - OpenCode",
        f'cd /d "{working_directory}"',
    ]
    for key in [
        "OPENCODE_CONFIG",
        "LACC_PROFILE",
        "LACC_OPENCODE_SECURITY_MODE",
        "LACC_OPENCODE_CAPABILITY_MODE",
        "LACC_OPENCODE_BUILD_STEPS",
        "LACC_OPENCODE_PLAN_STEPS",
        "LACC_OPENCODE_GENERAL_STEPS",
        "LACC_OPENCODE_EXPLORE_STEPS",
    ]:
        value = str(env.get(key, ""))
        escaped_value = value.replace('"', '""')
        lines.append(f'set "{key}={escaped_value}"')
    lines.append(f'"{executable_path}"')
    lines.append('set "OPENCODE_EXIT_CODE=%ERRORLEVEL%"')
    lines.append("if not \"%OPENCODE_EXIT_CODE%\"==\"0\" (")
    lines.append("  echo.")
    lines.append("  echo OpenCode je zavrsio sa kodom %OPENCODE_EXIT_CODE%.")
    lines.append("  echo Proveri model, konfiguraciju i logove ako se prozor odmah zatvorio.")
    lines.append("  pause")
    lines.append(")")
    lines.append("endlocal")
    launcher_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")


def _launch_opencode_launcher(launcher_path: Path) -> None:
    if not is_windows_platform():
        terminal_command = _build_linux_terminal_command(launcher_path)
        if terminal_command is None:
            raise RuntimeError(
                "Linux OpenCode launcher zahteva podrzan terminal emulator (npr. x-terminal-emulator ili gnome-terminal)."
            )
        subprocess.Popen(
            terminal_command,
            cwd=str(launcher_path.parent),
            close_fds=False,
        )
        return

    subprocess.Popen(
        [
            "cmd.exe",
            "/d",
            "/k",
            str(launcher_path),
        ],
        cwd=str(launcher_path.parent),
        creationflags=new_console_subprocess_creationflags(),
    )


def _build_linux_terminal_command(launcher_path: Path) -> list[str] | None:
    launcher = str(launcher_path)
    terminal_candidates = [
        ["x-terminal-emulator", "-e", launcher],
        ["gnome-terminal", "--", launcher],
        ["konsole", "-e", launcher],
        ["xfce4-terminal", "--command", launcher],
        ["xterm", "-e", launcher],
    ]
    for candidate in terminal_candidates:
        if shutil.which(candidate[0]):
            return candidate
    return None


def _ensure_executable_bit(path: Path) -> None:
    current_mode = path.stat().st_mode
    path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def load_opencode_step_schema_payload(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    return load_opencode_step_schema(config)


def save_opencode_settings_payload(
    payload: dict[str, object],
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    return apply_opencode_settings(payload, config)


def save_opencode_step_preset_payload(
    payload: dict[str, object],
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    return save_opencode_step_preset(payload, config)


def delete_opencode_step_preset_payload(
    preset_id: str,
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    return delete_opencode_step_preset(preset_id, config)


def _result(status: str, action: str, summary: str) -> dict[str, object]:
    return {
        "status": status,
        "action": action,
        "summary": summary,
        "details": {
            "returncode": 0 if status == "ok" else 1,
            "stdout": summary if status == "ok" else "",
            "stderr": "" if status == "ok" else summary,
        },
    }


def _security_mode_label(value: str) -> str:
    return {
        "strict": "Strogo ogranicen agent",
        "workspace-write": "Ogranicen agent sa blacklist pravilima",
        "open": "Potpuno otvoren agent",
    }.get(value, value)


def _capability_mode_label(value: str) -> str:
    return {
        "read-only": "1. Samo citanje fajlova",
        "read-write": "2. Citanje + izmena fajlova",
        "confirm-commands": "3. Citanje + izmena + komande uz potvrdu",
        "auto-commands": "4. Citanje + izmena + komande bez potvrde",
    }.get(value, value)


def _build_session_state(
    *,
    has_instances: bool,
    runtime_connected: bool,
    runtime_reason: str,
) -> tuple[str, str]:
    if has_instances and runtime_connected:
        return "connected", "OpenCode je otvoren i povezan sa runtime-om."
    if has_instances:
        reason = runtime_reason or "Runtime trenutno nije pokrenut."
        return "app-only", f"OpenCode je otvoren, ali backend nije spreman. {reason}"
    if runtime_connected:
        return "runtime-ready", "Runtime je spreman za novi OpenCode session."
    reason = runtime_reason or "Runtime trenutno nije pokrenut."
    return "idle", f"OpenCode je dostupan, ali backend jos nije spreman. {reason}"


def _build_open_action_contract(
    *,
    available: bool,
    config_exists: bool,
    session_state: str,
) -> tuple[str, str]:
    if not available:
        return "OpenCode nije instaliran", "OpenCode executable nije pronadjen."
    if not config_exists:
        return "OpenCode config nedostaje", "OpenCode managed config nije pronadjen."
    if session_state == "app-only":
        return "Pripremi backend za postojeci OpenCode", ""
    if session_state == "connected":
        return "OpenCode je vec otvoren", ""
    return "Open OpenCode", ""
