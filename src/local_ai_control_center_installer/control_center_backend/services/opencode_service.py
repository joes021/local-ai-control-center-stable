from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

from local_ai_control_center_installer.control_center_backend.config import (
    ControlCenterConfig,
    get_config,
)
from local_ai_control_center_installer.control_center_backend.services.settings_service import (
    apply_opencode_settings,
    delete_opencode_step_preset,
    load_effective_settings_state,
    load_opencode_step_schema,
    save_opencode_step_preset,
)
from local_ai_control_center_installer.opencode_bootstrap import load_opencode_manifest


def load_opencode_status_payload(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    executable_path = _resolve_opencode_executable_path(config)
    config_path = config.install_root / "config" / "opencode" / "managed-config.json"
    instances = detect_opencode_instances(executable_path)
    settings = load_effective_settings_state(config)

    return {
        "available": executable_path.is_file(),
        "active": bool(instances),
        "instanceCount": len(instances),
        "instances": instances,
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
    settings = load_effective_settings_state(config)
    if not executable_path.is_file():
        return _result("error", "open-opencode", "OpenCode executable nije pronadjen.")
    if not managed_config_path.is_file():
        return _result("error", "open-opencode", "OpenCode managed config nije pronadjen.")

    env = os.environ.copy()
    env["OPENCODE_CONFIG"] = str(managed_config_path)
    env["LACC_PROFILE"] = profile or str(settings["profile"])
    env["LACC_OPENCODE_SECURITY_MODE"] = str(settings["securityMode"])
    env["LACC_OPENCODE_CAPABILITY_MODE"] = str(settings["capabilityMode"])
    env["LACC_OPENCODE_BUILD_STEPS"] = str(settings["buildSteps"])
    env["LACC_OPENCODE_PLAN_STEPS"] = str(settings["planSteps"])
    env["LACC_OPENCODE_GENERAL_STEPS"] = str(settings["generalSteps"])
    env["LACC_OPENCODE_EXPLORE_STEPS"] = str(settings["exploreSteps"])
    log_path = config.install_root / "logs" / "opencode-launch.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        subprocess.Popen(
            [str(executable_path)],
            cwd=str(settings["workingDirectory"]),
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    return _result("ok", "open-opencode", "OpenCode je pokrenut.")


def detect_opencode_instances(executable_path: Path) -> list[dict[str, object]]:
    if not executable_path:
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

    payloads = parsed if isinstance(parsed, list) else [parsed]
    instances: list[dict[str, object]] = []
    for item in payloads:
        if not isinstance(item, dict):
            continue
        pid = item.get("ProcessId")
        if not isinstance(pid, int):
            continue
        instances.append(
            {
                "pid": pid,
                "name": str(item.get("Name", "") or ""),
                "commandLine": str(item.get("CommandLine", "") or ""),
            }
        )
    return instances


def _resolve_opencode_executable_path(config: ControlCenterConfig) -> Path:
    manifest = load_opencode_manifest()
    artifact = manifest["opencode_artifact"]
    launch = artifact["launch"]["executable_relative_path"]
    return config.install_root / artifact["install_subdir"] / launch


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
