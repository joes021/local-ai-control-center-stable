from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import subprocess
import time

from local_ai_control_center_installer.control_center_backend.config import (
    ControlCenterConfig,
    get_config,
)
from local_ai_control_center_installer.control_center_backend.services.network_service import (
    detect_tailscale_ip,
)
from local_ai_control_center_installer.control_center_backend.services.settings_service import (
    load_effective_settings_state,
    load_turboquant_config,
)
from local_ai_control_center_installer.control_center_backend.services.status_service import (
    find_runtime_pid,
    load_runtime_state,
    probe_server_health,
)
from local_ai_control_center_installer.server_verification import (
    _build_server_command,
    stop_managed_runtime_on_port,
    stop_server_process,
    ServerVerificationTarget,
)

RUNTIME_READY_TIMEOUT_SECONDS = 180.0
RUNTIME_READY_POLL_INTERVAL_SECONDS = 1.0


def load_server_status(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    runtime_state = load_runtime_state(config)
    health_status = probe_server_health(runtime_state["base_url"])
    pid = find_runtime_pid(int(runtime_state["port"]))
    status, health, reason = _build_server_state(health_status, pid)
    runtime_live_status, runtime_live_reason = _build_runtime_live_signal(
        health_status,
        pid,
    )
    if not bool(runtime_state.get("active_model_supported", True)) and pid is None:
        reason = str(runtime_state.get("active_model_reason", "") or reason)
        status = "stopped"
        health = "offline"
        runtime_live_status = "stopped"
        runtime_live_reason = reason

    tailscale_ip = detect_tailscale_ip()
    tailscale_url = ""
    if config.access_mode == "tailscale" and tailscale_ip:
        tailscale_url = f"http://{tailscale_ip}:{runtime_state['port']}/"

    has_warning = status != "started"
    warning_summary = reason if has_warning else ""
    warning_severity = "warning" if has_warning else ""

    return {
        "status": status,
        "lifecycleState": status,
        "port": runtime_state["port"],
        "health": health,
        "healthReason": reason,
        "pid": pid,
        "profile": runtime_state["profile"],
        "activeModel": runtime_state["active_model"],
        "activeRuntime": runtime_state["active_runtime"],
        "activeRuntimeLabel": _runtime_label(str(runtime_state["active_runtime"])),
        "runtimeLiveStatus": runtime_live_status,
        "runtimeLiveReason": runtime_live_reason,
        "lastReason": reason,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "healthUrl": f"{runtime_state['base_url']}/health",
        "webUrl": f"{runtime_state['base_url']}/",
        "localWebUrl": f"{runtime_state['base_url']}/",
        "tailscaleWebUrl": tailscale_url,
        "hasWarning": has_warning,
        "warningSeverity": warning_severity,
        "warningSummary": warning_summary,
    }


def start_server(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    runtime_state = load_runtime_state(config)
    port = int(runtime_state["port"])
    if find_runtime_pid(port) is not None:
        return _result(
            "ok",
            "start-server",
            "Runtime server je vec pokrenut.",
        )

    binary_path = Path(str(runtime_state["active_binary"] or ""))
    model_path = Path(str(runtime_state["active_model_path"] or ""))
    if not binary_path.is_file():
        return _result(
            "error",
            "start-server",
            "Aktivni runtime binar nije pronadjen.",
        )
    if not model_path.is_file():
        return _result(
            "error",
            "start-server",
            "Aktivni model nije pronadjen.",
        )
    if not bool(runtime_state.get("active_model_supported", True)):
        return _result(
            "error",
            "start-server",
            str(runtime_state.get("active_model_reason", "") or "Aktivni model nije podrzan za runtime start."),
        )

    command = _build_server_command(
        ServerVerificationTarget(
            server_executable=binary_path,
            model_id=str(runtime_state["active_model_id"]),
            model_path=model_path,
            active_model_config_path=config.install_root / "config" / "active-model.json",
        ),
        port,
        ctx_size=_resolve_runtime_context_size(config, runtime_state),
    )
    log_path = config.install_root / "logs" / "runtime-server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        subprocess.Popen(
            command,
            stdout=handle,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    return _result(
        "ok",
        "start-server",
        "Pokretanje runtime servera je poslato. Status ce se osveziti automatski.",
    )


def ensure_runtime_ready(
    config: ControlCenterConfig | None = None,
    *,
    timeout_seconds: float = RUNTIME_READY_TIMEOUT_SECONDS,
    poll_interval_seconds: float = RUNTIME_READY_POLL_INTERVAL_SECONDS,
    now_fn=time.monotonic,
    sleep_fn=time.sleep,
    health_probe=probe_server_health,
    pid_finder=find_runtime_pid,
) -> dict[str, object]:
    config = config or get_config()
    runtime_state = load_runtime_state(config)
    port = int(runtime_state["port"])
    base_url = str(runtime_state["base_url"])

    health_status = health_probe(base_url)
    runtime_pid = pid_finder(port)
    if health_status == "ready":
        return _result(
            "ok",
            "ensure-runtime-ready",
            "Runtime je vec spreman za OpenCode.",
        )

    if health_status == "offline" and runtime_pid is None:
        start_result = start_server(config)
        if start_result.get("status") != "ok":
            return {
                "status": "error",
                "action": "ensure-runtime-ready",
                "summary": str(start_result.get("summary", "") or "Runtime nije mogao da se pokrene."),
                "details": dict(start_result.get("details", {})),
            }

    deadline = now_fn() + max(timeout_seconds, 0.0)
    last_summary = "Runtime jos nije spreman za OpenCode."
    while now_fn() <= deadline:
        health_status = health_probe(base_url)
        runtime_pid = pid_finder(port)
        if health_status == "ready":
            return _result(
                "ok",
                "ensure-runtime-ready",
                "Runtime je spreman za OpenCode.",
            )
        if health_status == "loading":
            last_summary = "Runtime se jos ucitava za OpenCode."
        elif runtime_pid is not None:
            last_summary = "Runtime proces postoji, ali health jos nije spreman."
        else:
            last_summary = "Runtime nije ostao pokrenut tokom pripreme za OpenCode."
        sleep_fn(poll_interval_seconds)

    return _result(
        "error",
        "ensure-runtime-ready",
        f"Runtime nije postao spreman za OpenCode u roku od {int(timeout_seconds)}s. {last_summary}",
    )


def stop_server(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    runtime_state = load_runtime_state(config)
    port = int(runtime_state["port"])
    pid = find_runtime_pid(port)
    if pid is None:
        return _result(
            "ok",
            "stop-server",
            "Runtime server je vec zaustavljen.",
        )

    binary_path = Path(str(runtime_state["active_binary"] or ""))
    if not binary_path.is_file():
        return _result(
            "error",
            "stop-server",
            "Aktivni runtime binar nije pronadjen.",
        )

    if stop_managed_runtime_on_port(port, binary_path, config.install_root):
        return _result("ok", "stop-server", "Runtime server je zaustavljen.")

    return _result(
        "error",
        "stop-server",
        "Runtime server nije mogao bezbedno da se zaustavi.",
    )


def open_server_web(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    runtime_state = load_runtime_state(config)
    url = f"{runtime_state['base_url']}/"
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f"Start-Process '{url}'",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode == 0:
        return _result("ok", "open-server-web", f"Otvoren runtime web: {url}")
    return {
        "status": "error",
        "action": "open-server-web",
        "summary": completed.stderr.strip()
        or completed.stdout.strip()
        or "Otvaranje runtime web-a nije uspelo.",
        "details": {
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        },
    }


def _build_server_state(
    health_status: str,
    pid: int | None,
) -> tuple[str, str, str]:
    if health_status == "ready":
        return "started", "ok", "Runtime health endpoint odgovara."
    if health_status == "loading":
        return "warming", "loading", "Runtime endpoint odgovara, ali model se jos loading."
    if pid is not None:
        return "warming", "loading", "Runtime proces postoji, ali health jos nije spreman."
    return "stopped", "offline", "Runtime trenutno nije pokrenut."


def _build_runtime_live_signal(
    health_status: str,
    pid: int | None,
) -> tuple[str, str]:
    if health_status == "ready":
        return "started", "Runtime health endpoint odgovara."
    if health_status == "loading":
        return "warming", "Runtime odgovara, ali model se jos ucitava."
    if pid is not None:
        return "warming", "Runtime proces postoji, ali health jos nije spreman."
    return "stopped", "Runtime trenutno nije pokrenut."


def _runtime_label(runtime_name: str) -> str:
    return {
        "llama.cpp": "llama.cpp",
        "turboquant": "TurboQuant",
    }.get(runtime_name, runtime_name)


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


def _resolve_runtime_context_size(
    config: ControlCenterConfig,
    runtime_state: dict[str, object],
) -> int | None:
    active_runtime = str(runtime_state.get("active_runtime", "") or "").strip().lower()
    if active_runtime == "turboquant":
        turbo_config = load_turboquant_config(config)
        return _positive_int_or_none(turbo_config.get("context"))
    settings = load_effective_settings_state(config)
    return _positive_int_or_none(settings.get("context"))


def _positive_int_or_none(value: object) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
