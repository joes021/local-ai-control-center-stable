from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import shlex
import tempfile

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
from local_ai_control_center_installer.download_plan import (
    OPENCODE_ARTIFACT_DOWNLOAD_KEY,
    DownloadPlan,
    DownloadPlanItem,
)
from local_ai_control_center_installer.downloads import download_file
from local_ai_control_center_installer.opencode_bootstrap import (
    apply_opencode_bootstrap,
    load_opencode_manifest,
)
from local_ai_control_center_installer.platform_paths import (
    is_windows_platform,
    new_console_subprocess_creationflags,
)
from local_ai_control_center_installer.runtime_bootstrap import load_runtime_endpoint_config
from local_ai_control_center_installer.session import InstallerSession


def load_opencode_status_payload(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    executable_path = _resolve_opencode_executable_path(config)
    config_path = config.install_root / "config" / "opencode" / "managed-config.json"
    launcher_path = config.install_root / "control-center" / (
        "Open-OpenCode.cmd" if is_windows_platform() else "Open-OpenCode.sh"
    )
    instances = detect_opencode_instances(executable_path)
    launcher_instances = detect_opencode_launcher_instances(launcher_path)
    settings = load_effective_settings_state(config)
    runtime_state = load_runtime_state(config)
    runtime_connected = str(runtime_state.get("runtime_live_status", "")) == "started"
    session_state, session_summary = _build_session_state(
        has_instances=bool(instances),
        launch_in_progress=bool(launcher_instances),
        runtime_connected=runtime_connected,
        runtime_reason=str(runtime_state.get("runtime_live_reason", "") or ""),
    )
    can_open, open_action_label, open_blocked_reason = _resolve_open_action_contract(
        available=executable_path.is_file(),
        config_exists=config_path.is_file(),
        session_state=session_state,
    )
    can_bootstrap, bootstrap_action_label, bootstrap_blocked_reason = _build_bootstrap_action_contract(
        config=config,
        available=executable_path.is_file(),
        config_exists=config_path.is_file(),
        runtime_state=runtime_state,
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
        "canBootstrap": can_bootstrap,
        "bootstrapActionLabel": bootstrap_action_label,
        "bootstrapBlockedReason": bootstrap_blocked_reason,
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
        "webSearchMode": str(settings.get("webSearchMode", "off") or "off"),
        "webSearchPromptPrefix": str(settings.get("webSearchPromptPrefix", "/web") or "/web"),
        "localProviderUsesSearchProxy": True,
        "localProviderSearchSummary": _build_local_provider_search_summary(settings),
        "launchPreview": _build_opencode_launch_preview(
            config=config,
            executable_path=executable_path,
            managed_config_path=config_path,
            settings=settings,
        ),
        "auditRiskLevel": "",
        "auditSummary": (
            "Installer-managed OpenCode bootstrap je spreman."
            if executable_path.is_file()
            else "OpenCode nije instaliran."
        ),
    }


def bootstrap_opencode_payload(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    runtime_state = load_runtime_state(config)
    can_bootstrap, action_label, blocked_reason = _build_bootstrap_action_contract(
        config=config,
        available=_resolve_opencode_executable_path(config).is_file(),
        config_exists=config.opencode_managed_config_path.is_file(),
        runtime_state=runtime_state,
    )
    if not can_bootstrap:
        return _result(
            "error",
            "bootstrap-opencode",
            blocked_reason or f"{action_label} trenutno nije dostupan.",
        )

    session = InstallerSession(
        install_opencode=True,
        server_verification_status="ready",
        install_root=str(config.install_root),
        verified_server_url=config.ui_url,
        runtime_endpoint_config_path=str(config.runtime_endpoint_config_path),
        active_model_config_path=str(config.active_model_config_path),
    )
    session.download_plan = _build_opencode_bootstrap_download_plan()
    temp_root = Path(tempfile.gettempdir())
    updated = apply_opencode_bootstrap(
        session,
        temp_root=temp_root,
        download_archive=lambda url, destination, *, plan_item=None: download_file(
            url,
            destination,
            plan_item=plan_item,
        ),
    )
    if updated.opencode_artifact_status != "ready" or updated.last_successful_step != "opencode-config":
        summary = str(
            updated.error_message
            or "OpenCode bootstrap nije uspeo."
        ).strip() or "OpenCode bootstrap nije uspeo."
        if updated.failing_step:
            summary = f"{summary} Korak: {updated.failing_step}."
        return _result("error", "bootstrap-opencode", summary)

    try:
        prepare_opencode_launcher(config=config)
    except (FileNotFoundError, OSError):
        return _result(
            "error",
            "bootstrap-opencode",
            "OpenCode artifact je preuzet, ali launcher nije mogao da se pripremi.",
        )

    if _resolve_opencode_executable_path(config).is_file():
        return _result(
            "ok",
            "bootstrap-opencode",
            "OpenCode je instaliran ili popravljen i spreman za Tuning Lab i OpenCode tab.",
        )
    return _result("error", "bootstrap-opencode", "OpenCode executable i dalje nije pronađen posle bootstrap-a.")


def open_opencode(
    profile: str = "",
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    executable_path = _resolve_opencode_executable_path(config)
    managed_config_path = config.install_root / "config" / "opencode" / "managed-config.json"
    if not executable_path.is_file():
        return _result("error", "open-opencode", "OpenCode executable nije pronađen.")
    if not managed_config_path.is_file():
        return _result("error", "open-opencode", "OpenCode managed config nije pronađen.")
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
            "OpenCode je već otvoren; backend je pripremljen za postojeću sesiju.",
        )

    launcher_path = prepare_opencode_launcher(config=config, profile=profile)
    existing_launchers = detect_opencode_launcher_instances(launcher_path)
    if existing_launchers:
        return _result(
            "ok",
            "open-opencode",
            "OpenCode launch je već u toku; sačekaj da se postojeći launcher završi.",
        )

    log_path = config.install_root / "logs" / "opencode-launch.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
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
        raise FileNotFoundError(f"OpenCode executable nije pronađen: {executable_path}")
    if not managed_config_path.is_file():
        raise FileNotFoundError(
            f"OpenCode managed config nije pronađen: {managed_config_path}"
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


def detect_opencode_launcher_instances(launcher_path: Path) -> list[dict[str, object]]:
    if not is_windows_platform():
        return []
    launcher_token = _normalize_windows_path_token(str(launcher_path))
    if not launcher_token:
        return []
    payloads = _query_shell_launcher_processes()
    if not payloads:
        return []
    instances: list[dict[str, object]] = []
    for item in payloads:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("Name") or "").strip().lower()
        if name != "cmd.exe":
            continue
        pid = item.get("pid") or item.get("ProcessId")
        if not isinstance(pid, int):
            continue
        command_line = str(item.get("commandLine") or item.get("CommandLine") or "")
        if not _command_line_matches_executable(command_line, launcher_token):
            continue
        instances.append(
            {
                "pid": pid,
                "name": name,
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


def _query_shell_launcher_processes() -> list[dict[str, object]]:
    if not is_windows_platform():
        return []
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            (
                "$matches = Get-CimInstance Win32_Process "
                "| Where-Object { $_.Name -eq 'cmd.exe' } "
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
        *_build_windows_opencode_launcher_guard_lines(
            launcher_path=launcher_path,
            executable_path=executable_path,
        ),
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
    lines.append("  echo OpenCode je završio sa kodom %OPENCODE_EXIT_CODE%.")
    lines.append("  echo Proveri model, konfiguraciju i logove ako se prozor odmah zatvorio.")
    lines.append("  pause")
    lines.append(")")
    lines.append("endlocal")
    launcher_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")


def _build_windows_opencode_launcher_guard_lines(
    *,
    launcher_path: Path,
    executable_path: Path,
) -> list[str]:
    launcher_token = _quote_powershell_string(str(launcher_path))
    executable_token = _quote_powershell_string(str(executable_path))
    powershell_script = (
        f"$launcherPath = {launcher_token}; "
        f"$executablePath = {executable_token}; "
        "$launcherMatches = Get-CimInstance Win32_Process "
        "| Where-Object { $_.Name -eq 'cmd.exe' -and $_.CommandLine -like ('*' + $launcherPath + '*') }; "
        "$runtimeMatches = Get-CimInstance Win32_Process "
        "| Where-Object { $_.Name -eq 'opencode.exe' -and $_.CommandLine -like ('*' + $executablePath + '*') }; "
        "if (($runtimeMatches | Measure-Object).Count -gt 0 -or ($launcherMatches | Measure-Object).Count -gt 1) { exit 0 }; "
        "exit 1"
    )
    return [
        f'powershell -NoProfile -ExecutionPolicy Bypass -Command "{powershell_script}" >nul 2>nul',
        'if "%ERRORLEVEL%"=="0" (',
        "  echo OpenCode launch je vec u toku ili je sesija vec otvorena.",
        "  endlocal",
        "  exit /b 0",
        ")",
    ]


def _build_opencode_launch_preview(
    *,
    config: ControlCenterConfig,
    executable_path: Path,
    managed_config_path: Path,
    settings: dict[str, object],
) -> dict[str, object]:
    launcher_name = "Open-OpenCode.cmd" if is_windows_platform() else "Open-OpenCode.sh"
    launcher_path = config.install_root / "control-center" / launcher_name
    env = _build_opencode_launch_environment(
        managed_config_path=managed_config_path,
        settings=settings,
        profile="",
    )
    env_items = [
        {"key": key, "value": str(env.get(key, ""))}
        for key in [
            "OPENCODE_CONFIG",
            "LACC_PROFILE",
            "LACC_OPENCODE_SECURITY_MODE",
            "LACC_OPENCODE_CAPABILITY_MODE",
            "LACC_OPENCODE_BUILD_STEPS",
            "LACC_OPENCODE_PLAN_STEPS",
            "LACC_OPENCODE_GENERAL_STEPS",
            "LACC_OPENCODE_EXPLORE_STEPS",
        ]
    ]
    if not is_windows_platform():
        shell_command = f'bash "{launcher_path}"'
        powershell_command = "\n".join(
            [
                f'cd "{settings["workingDirectory"]}"',
                *(f'export {item["key"]}="{item["value"]}"' for item in env_items),
                f'"{executable_path}"',
            ]
        )
        return {
            "shellLabel": "Shell",
            "launcherPath": str(launcher_path),
            "launcherCommand": shell_command,
            "powershellCommand": powershell_command,
            "workingDirectory": str(settings["workingDirectory"]),
            "environment": env_items,
            "managedConfig": _build_managed_opencode_config_preview(managed_config_path),
            "generationSummary": _build_generation_defaults_summary(settings),
            "summary": (
                "OpenCode koristi managed config, a local-lacc inference podrazumevana sampling "
                "podesavanja dobija kroz runtime proxy sloj iz Control Center-a."
            ),
        }

    powershell_lines = [
        f'Set-Location "{settings["workingDirectory"]}"',
        *(
            f'$env:{item["key"]} = "{_escape_powershell_value(str(item["value"]))}"'
            for item in env_items
        ),
        f'& "{executable_path}"',
    ]
    return {
        "shellLabel": "PowerShell",
        "launcherPath": str(launcher_path),
        "launcherCommand": f'cmd.exe /d /c "{launcher_path}"',
        "powershellCommand": "\n".join(powershell_lines),
        "workingDirectory": str(settings["workingDirectory"]),
        "environment": env_items,
        "managedConfig": _build_managed_opencode_config_preview(managed_config_path),
        "generationSummary": _build_generation_defaults_summary(settings),
        "summary": (
            "OpenCode model i provider dolaze iz managed-config.json, a local-lacc u sebi koristi "
            "trenutni runtime, aktivni model i sampling podrazumevana podesavanja iz Control Center-a."
        ),
    }


def _launch_opencode_launcher(launcher_path: Path) -> None:
    if not is_windows_platform():
        terminal_command = _build_linux_terminal_command(launcher_path)
        if terminal_command is None:
            raise RuntimeError(
                "Linux OpenCode launcher zahteva podržan terminal emulator (npr. x-terminal-emulator ili gnome-terminal)."
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
            "/c",
            str(launcher_path),
        ],
        cwd=str(launcher_path.parent),
        creationflags=new_console_subprocess_creationflags(),
    )


def _build_managed_opencode_config_preview(managed_config_path: Path) -> dict[str, object]:
    fallback = {
        "model": "",
        "selectedProvider": "",
        "localProviderBaseUrl": "",
        "enabledProviders": [],
    }
    if not managed_config_path.is_file():
        return fallback
    try:
        payload = json.loads(managed_config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback
    if not isinstance(payload, dict):
        return fallback

    model = str(payload.get("model", "") or "")
    selected_provider = model.split("/", 1)[0] if "/" in model else ""
    provider_root = payload.get("provider")
    if not isinstance(provider_root, dict):
        provider_root = payload.get("providers")
    if not isinstance(provider_root, dict):
        provider_root = {}

    enabled_providers = payload.get("enabled_providers")
    if isinstance(enabled_providers, list):
        enabled_provider_list = [str(item) for item in enabled_providers if str(item).strip()]
    else:
        enabled_provider_list = [str(key) for key in provider_root.keys() if str(key).strip()]

    provider_id = selected_provider or "local-lacc"
    provider_entry = provider_root.get(provider_id)
    if not isinstance(provider_entry, dict):
        provider_entry = provider_root.get("local-lacc")

    base_url = ""
    if isinstance(provider_entry, dict):
        options = provider_entry.get("options")
        if isinstance(options, dict):
            base_url = str(options.get("baseURL", "") or options.get("baseUrl", "") or "")

    return {
        "model": model,
        "selectedProvider": selected_provider,
        "localProviderBaseUrl": base_url,
        "enabledProviders": enabled_provider_list,
    }


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


def _escape_powershell_value(value: str) -> str:
    return value.replace('"', '`"')


def _quote_powershell_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


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


def _build_opencode_bootstrap_download_plan() -> DownloadPlan:
    try:
        manifest = load_opencode_manifest()
    except (OSError, ValueError):
        return DownloadPlan(items=())

    artifact = manifest["opencode_artifact"]
    size_bytes = artifact.get("size_bytes")
    normalized_size = size_bytes if isinstance(size_bytes, int) else None
    return DownloadPlan(
        items=(
            DownloadPlanItem(
                key=OPENCODE_ARTIFACT_DOWNLOAD_KEY,
                label="OpenCode",
                url=str(artifact["url"]),
                destination_hint=str(artifact["install_subdir"]),
                size_bytes=normalized_size,
                queue_index=1,
                queue_total=1,
            ),
        )
    )


def _security_mode_label(value: str) -> str:
    return {
        "strict": "Strogo ograničen agent",
        "workspace-write": "Ograničen agent sa blacklist pravilima",
        "open": "Potpuno otvoren agent",
    }.get(value, value)


def _capability_mode_label(value: str) -> str:
    return {
        "read-only": "1. Samo čitanje fajlova",
        "read-write": "2. Čitanje + izmena fajlova",
        "confirm-commands": "3. Čitanje + izmena + komande uz potvrdu",
        "auto-commands": "4. Čitanje + izmena + komande bez potvrde",
    }.get(value, value)


def _build_local_provider_search_summary(settings: dict[str, object]) -> str:
    mode = str(settings.get("webSearchMode", "off") or "off")
    prefix = str(settings.get("webSearchPromptPrefix", "/web") or "/web")
    if mode == "always":
        return "Local-lacc provider uvek prolazi kroz lokalni SearxNG search augmentation sloj."
    if mode == "on-demand":
        return (
            "Local-lacc provider koristi lokalni SearxNG search sloj samo kada prompt "
            f"krene prefiksom {prefix}."
        )
    return "Local-lacc provider trenutno radi bez automatskog web search augmentation-a."


def _build_generation_defaults_summary(settings: dict[str, object]) -> str:
    return (
        f"temp {settings.get('temperature', 0.8)} | top-k {settings.get('topK', 40)} | "
        f"top-p {settings.get('topP', 0.95)} | min-p {settings.get('minP', 0.05)} | "
        f"repeat {settings.get('repeatPenalty', 1.0)} / last-n {settings.get('repeatLastN', 64)} | "
        f"presence {settings.get('presencePenalty', 0.0)} | "
        f"frequency {settings.get('frequencyPenalty', 0.0)} | seed {settings.get('seed', -1)}"
    )


def _build_session_state(
    *,
    has_instances: bool,
    launch_in_progress: bool,
    runtime_connected: bool,
    runtime_reason: str,
) -> tuple[str, str]:
    if has_instances and runtime_connected:
        return "connected", "OpenCode je otvoren i povezan sa runtime-om."
    if has_instances:
        reason = runtime_reason or "Runtime trenutno nije pokrenut."
        return "app-only", f"OpenCode je otvoren, ali backend nije spreman. {reason}"
    if launch_in_progress:
        return "launching", "OpenCode launch je u toku i čeka se da se sesija stabilizuje."
    if runtime_connected:
        return "runtime-ready", "Runtime je spreman za novi OpenCode session."
    reason = runtime_reason or "Runtime trenutno nije pokrenut."
    return "idle", f"OpenCode je dostupan, ali backend još nije spreman. {reason}"


def _build_open_action_contract(
    *,
    available: bool,
    config_exists: bool,
    session_state: str,
) -> tuple[str, str]:
    if not available:
        return "OpenCode nije instaliran", "OpenCode executable nije pronađen."
    if not config_exists:
        return "OpenCode config nedostaje", "OpenCode managed config nije pronađen."
    if session_state == "app-only":
        return "Pripremi backend za postojeći OpenCode", ""
    if session_state == "connected":
        return "OpenCode je već otvoren", ""
    return "Otvori OpenCode", ""


def _resolve_open_action_contract(
    *,
    available: bool,
    config_exists: bool,
    session_state: str,
) -> tuple[bool, str, str]:
    if not available:
        return False, "OpenCode nije instaliran", "OpenCode executable nije pronađen."
    if not config_exists:
        return False, "OpenCode config nedostaje", "OpenCode managed config nije pronađen."
    if session_state == "launching":
        return False, "OpenCode launch je u toku", "Sačekaj da se postojeći OpenCode launcher završi."
    if session_state == "app-only":
        return True, "Pripremi backend za postojeći OpenCode", ""
    if session_state == "connected":
        return True, "OpenCode je već otvoren", ""
    return True, "Otvori OpenCode", ""


def _build_bootstrap_action_contract(
    *,
    config: ControlCenterConfig,
    available: bool,
    config_exists: bool,
    runtime_state: dict[str, object],
) -> tuple[bool, str, str]:
    label = "Reinstall / popravi OpenCode" if available and config_exists else "Instaliraj OpenCode"
    active_model_id = str(runtime_state.get("active_model_id", "") or "").strip().lower()
    active_model_label = str(runtime_state.get("active_model", "") or "").strip().lower()
    active_model_path = Path(str(runtime_state.get("active_model_path", "") or ""))
    if (
        not active_model_path.is_file()
        or not active_model_id
        or active_model_id == "unknown"
        or active_model_label in {"", "unknown", "nema aktivnog modela"}
    ):
        return (
            False,
            label,
            "Aktivan model nije podešen. Aktiviraj lokalni model pre instalacije OpenCode-a.",
        )
    try:
        load_runtime_endpoint_config(config.runtime_endpoint_config_path)
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return (
            False,
            label,
            "Runtime endpoint konfiguracija nedostaje ili je neispravna. Pokreni ili aktiviraj runtime pre instalacije OpenCode-a.",
        )
    return True, label, ""
