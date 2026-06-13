from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import os
from pathlib import Path
import re
import subprocess
import threading
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
    classify_runtime_model_support,
    find_runtime_pid,
    load_runtime_state,
    probe_server_health,
    runtime_supports_draft_mtp,
)
from local_ai_control_center_installer.server_verification import (
    _build_server_command,
    is_managed_runtime_port_owned_by_installation,
    stop_managed_runtime_on_port,
    stop_server_process,
    ServerVerificationTarget,
)

RUNTIME_READY_TIMEOUT_SECONDS = 180.0
RUNTIME_READY_POLL_INTERVAL_SECONDS = 1.0
_START_SERVER_READY_TIMEOUT_SECONDS = 2.0
_START_SERVER_READY_POLL_INTERVAL_SECONDS = 0.1
_START_SERVER_LOG_EXCERPT_CHARS = 4000
_START_SERVER_EXIT_LOG_WAIT_SECONDS = 0.6
_START_SERVER_EXIT_LOG_POLL_INTERVAL_SECONDS = 0.1
_START_SERVER_LOADING_STABILITY_SECONDS = 1.0
_POWERSHELL_SAFE_ARGUMENT_RE = re.compile(r"^[A-Za-z0-9_./:-]+$")
_INVALID_MAIN_GPU_RE = re.compile(r"invalid value for main_gpu", re.IGNORECASE)
_PROJECTED_DEVICE_MEMORY_RE = re.compile(
    r"projected to use (?P<used>\d+) MiB of device memory",
    re.IGNORECASE,
)
_PROJECTED_HOST_MEMORY_RE = re.compile(
    r"projected to use (?P<used>\d+) MiB of host memory",
    re.IGNORECASE,
)
_DEVICE_LABEL_RE = re.compile(
    r"using device [A-Z0-9]+ \((?P<label>[^)]+)\)",
    re.IGNORECASE,
)
_OFFLOADED_LAYERS_RE = re.compile(
    r"offloaded (?P<gpu>\d+)/(?P<total>\d+) layers to GPU",
    re.IGNORECASE,
)
_MODEL_BUFFER_RE = re.compile(
    r"model buffer size =\s+(?P<value>\d+(?:\.\d+)?) MiB",
    re.IGNORECASE,
)
_CPU_MAPPED_MODEL_BUFFER_RE = re.compile(
    r"CPU_Mapped model buffer size =\s+(?P<value>\d+(?:\.\d+)?) MiB",
    re.IGNORECASE,
)
_KV_BUFFER_RE = re.compile(
    r"KV buffer size =\s+(?P<value>\d+(?:\.\d+)?) MiB",
    re.IGNORECASE,
)
_COMPUTE_BUFFER_RE = re.compile(
    r"compute buffer size =\s+(?P<value>\d+(?:\.\d+)?) MiB",
    re.IGNORECASE,
)
_CTX_SIZE_FLAG_RE = re.compile(r"(?:^|\s)--ctx-size\s+(?P<value>\d+)(?:\s|$)", re.IGNORECASE)
RUNTIME_PROCESS_COMMAND_LINE_CACHE_TTL_SECONDS = 5.0
_RUNTIME_PROCESS_COMMAND_LINE_CACHE_LOCK = threading.Lock()
_RUNTIME_PROCESS_COMMAND_LINE_CACHE: dict[int, tuple[float, str]] = {}


def load_server_status(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    runtime_state = load_runtime_state(config)
    active_runtime = str(runtime_state.get("active_runtime", "") or "").strip().lower()
    active_binary_path = Path(str(runtime_state.get("active_binary", "") or ""))
    runtime_diagnostics = load_runtime_diagnostics(
        runtime_name=active_runtime,
        launch_arguments=_load_runtime_launch_argument_values(
            config,
            runtime_state,
            runtime_name=active_runtime,
            binary_path=active_binary_path,
        ),
        log_path=config.install_root / "logs" / "runtime-server.log",
    )
    health_status = probe_server_health(runtime_state["base_url"])
    pid = find_runtime_pid(int(runtime_state["port"]))
    status, health, reason = _build_server_state(health_status, pid)
    runtime_live_status, runtime_live_reason = _build_runtime_live_signal(
        health_status,
        pid,
    )
    runtime_diagnostics = _attach_runtime_context_alignment(
        runtime_diagnostics,
        config=config,
        runtime_state=runtime_state,
        runtime_name=active_runtime,
        runtime_pid=pid,
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

    selection_warning = str(runtime_state.get("active_binary_source", "") or "") == "fallback"
    has_warning = status != "started" or selection_warning
    warning_summary = ""
    if selection_warning:
        warning_summary = str(runtime_state.get("runtime_selection_summary", "") or "")
    elif has_warning:
        warning_summary = reason
    warning_severity = "warning" if has_warning else ""
    can_start, start_blocked_reason = _build_start_capability(runtime_state)
    can_open_web = status in {"started", "warming"}
    open_web_blocked_reason = (
        "" if can_open_web else "Runtime web nije spreman dok server nije pokrenut ili health ne odgovara."
    )
    can_stop = pid is not None or status in {"started", "warming", "degraded"}
    stop_blocked_reason = "" if can_stop else "Runtime server je već zaustavljen."

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
        "requestedRuntimeLabel": _runtime_label(str(runtime_state["requested_runtime"])),
        "runtimeSelectionSummary": str(runtime_state.get("runtime_selection_summary", "") or ""),
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
        "canStart": can_start,
        "startBlockedReason": start_blocked_reason,
        "canStop": can_stop,
        "stopBlockedReason": stop_blocked_reason,
        "canOpenWeb": can_open_web,
        "openWebBlockedReason": open_web_blocked_reason,
        "runtimeDiagnostics": runtime_diagnostics,
        "commandPreview": _build_server_command_preview(config, runtime_state),
    }


def start_server(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    runtime_state = load_runtime_state(config)
    port = int(runtime_state["port"])
    health_status = probe_server_health(str(runtime_state["base_url"]))
    existing_pid = find_runtime_pid(port)

    binary_path = Path(str(runtime_state["active_binary"] or ""))
    model_path = Path(str(runtime_state["active_model_path"] or ""))
    if not binary_path.is_file():
        return _result(
            "error",
            "start-server",
            "Aktivni runtime binar nije pronađen.",
        )
    if not model_path.is_file():
        return _result(
            "error",
            "start-server",
            "Aktivni model nije pronađen.",
        )
    if not bool(runtime_state.get("active_model_supported", True)):
        return _result(
            "error",
            "start-server",
            str(runtime_state.get("active_model_reason", "") or "Aktivni model nije podržan za runtime start."),
        )
    restart_summary = "Pokretanje runtime servera je poslato. Status će se osvežiti automatski."
    if existing_pid is not None:
        if health_status == "ready":
            return _result(
                "ok",
                "start-server",
                "Runtime server je već pokrenut i health endpoint odgovara.",
            )
        if health_status == "loading":
            return _result(
                "ok",
                "start-server",
                "Runtime server je već u fazi zagrevanja i health još nije spreman.",
            )
        if not is_managed_runtime_port_owned_by_installation(
            port,
            binary_path,
            config.install_root,
        ):
            return _result(
                "error",
                "start-server",
                f"Port {port} je zauzet procesom koji ne pripada ovoj instalaciji, a runtime health ne odgovara.",
            )
        if not stop_managed_runtime_on_port(port, binary_path, config.install_root):
            return _result(
                "error",
                "start-server",
                "Postojeći runtime proces nije odgovarao na health proveru i nije mogao bezbedno da se restartuje.",
            )
        restart_summary = "Neodgovarajući runtime proces je zaustavljen i restartovan."

    target = ServerVerificationTarget(
        server_executable=binary_path,
        model_id=str(runtime_state["active_model_id"]),
        model_path=model_path,
        active_model_config_path=config.install_root / "config" / "active-model.json",
    )
    launch_arguments = _load_runtime_launch_argument_values(
        config,
        runtime_state,
        runtime_name=str(runtime_state.get("active_runtime", "") or ""),
        binary_path=binary_path,
    )
    launch_result = _launch_runtime_with_main_gpu_fallback(
        target=target,
        port=port,
        base_url=str(runtime_state["base_url"]),
        ctx_size=_resolve_runtime_context_size(config, runtime_state),
        spec_type=_resolve_spec_type(runtime_state, binary_path),
        launch_arguments=launch_arguments,
        log_path=config.install_root / "logs" / "runtime-server.log",
    )
    if str(launch_result.get("status", "")) != "ok":
        return _result(
            "error",
            "start-server",
            str(launch_result.get("summary", "") or "Runtime nije mogao da se pokrene."),
        )

    log_path = config.install_root / "logs" / "runtime-server.log"
    summary = restart_summary
    if bool(launch_result.get("fallbackApplied")):
        summary = f"{restart_summary} {str(launch_result.get('fallbackReason', '') or '').strip()}".strip()

    return _result(
        "ok",
        "start-server",
        summary,
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
            "Runtime je već spreman za OpenCode.",
        )

    if health_status == "offline":
        start_result = start_server(config)
        if start_result.get("status") != "ok":
            return {
                "status": "error",
                "action": "ensure-runtime-ready",
                "summary": str(start_result.get("summary", "") or "Runtime nije mogao da se pokrene."),
                "details": dict(start_result.get("details", {})),
            }

    deadline = now_fn() + max(timeout_seconds, 0.0)
    last_summary = "Runtime još nije spreman za OpenCode."
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
            last_summary = "Runtime se još učitava za OpenCode."
        elif runtime_pid is not None:
            last_summary = "Runtime proces postoji, ali health endpoint još ne odgovara."
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
        if _stop_orphaned_runtime_processes(config.install_root):
            return _result(
                "ok",
                "stop-server",
                "Zaustavljeni su preostali runtime procesi bez aktivnog listener-a.",
            )
        return _result(
            "ok",
            "stop-server",
            "Runtime server je već zaustavljen.",
        )

    binary_path = Path(str(runtime_state["active_binary"] or ""))
    if not binary_path.is_file():
        return _result(
            "error",
            "stop-server",
            "Aktivni runtime binar nije pronađen.",
        )

    if stop_managed_runtime_on_port(port, binary_path, config.install_root):
        return _result("ok", "stop-server", "Runtime server je zaustavljen.")
    if _stop_orphaned_runtime_processes(config.install_root) and find_runtime_pid(port) is None:
        return _result("ok", "stop-server", "Runtime server je zaustavljen.")

    return _result(
        "error",
        "stop-server",
        "Runtime server nije mogao bezbedno da se zaustavi.",
    )


def restart_server(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    stop_result = stop_server(config)
    if str(stop_result.get("status", "")) != "ok":
        return _result(
            "error",
            "restart-server",
            str(stop_result.get("summary", "") or "Runtime server nije mogao da se zaustavi pre restarta."),
        )

    start_result = start_server(config)
    if str(start_result.get("status", "")) != "ok":
        return _result(
            "error",
            "restart-server",
            str(start_result.get("summary", "") or "Runtime server nije mogao da se pokrene posle restarta."),
        )

    return _result(
        "ok",
        "restart-server",
        "Runtime server je restartovan da poravna context sa sačuvanim podešavanjem.",
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
        return "warming", "loading", "Runtime endpoint odgovara, ali model se još loading."
    if pid is not None:
        return "degraded", "offline", "Runtime proces postoji, ali health endpoint ne odgovara."
    return "stopped", "offline", "Runtime trenutno nije pokrenut."


def _launch_runtime_with_main_gpu_fallback(
    *,
    target: ServerVerificationTarget,
    port: int,
    base_url: str,
    ctx_size: int,
    spec_type: str | None,
    launch_arguments: dict[str, object],
    log_path: Path,
) -> dict[str, object]:
    command = _build_server_command(
        target,
        port,
        ctx_size=ctx_size,
        spec_type=spec_type,
        **launch_arguments,
    )
    process = _launch_runtime_process(command, log_path)
    start_signal = _wait_for_runtime_start_signal(base_url, process)
    if str(start_signal.get("state", "")) != "exited":
        return {
            "status": "ok",
            "command": command,
            "launchArguments": launch_arguments,
            "fallbackApplied": False,
            "fallbackReason": "",
        }

    log_excerpt = _read_runtime_log_excerpt_after_exit(
        log_path,
        prefer_pattern=_INVALID_MAIN_GPU_RE,
    )
    if _should_retry_runtime_without_explicit_main_gpu(
        launch_arguments=launch_arguments,
        log_excerpt=log_excerpt,
    ):
        fallback_launch_arguments = dict(launch_arguments)
        fallback_launch_arguments.pop("main_gpu", None)
        fallback_launch_arguments.pop("split_mode", None)
        fallback_command = _build_server_command(
            target,
            port,
            ctx_size=ctx_size,
            spec_type=spec_type,
            **fallback_launch_arguments,
        )
        process = _launch_runtime_process(fallback_command, log_path)
        fallback_signal = _wait_for_runtime_start_signal(base_url, process)
        fallback_reason = (
            "Runtime je odbio eksplicitni `--main-gpu`, pa je start ponovljen bez "
            "`--main-gpu` i `--split-mode`."
        )
        if str(fallback_signal.get("state", "")) != "exited":
            return {
                "status": "ok",
                "command": fallback_command,
                "launchArguments": fallback_launch_arguments,
                "fallbackApplied": True,
                "fallbackReason": fallback_reason,
            }
        fallback_log_excerpt = _read_runtime_log_excerpt_after_exit(log_path)
        return {
            "status": "error",
            "summary": (
                "Runtime nije mogao da se pokrene ni posle fallback pokušaja bez "
                "eksplicitnog `--main-gpu` izbora. "
                + _format_runtime_start_failure_details(fallback_log_excerpt)
            ),
        }

    return {
        "status": "error",
        "summary": "Runtime nije mogao da se pokrene. " + _format_runtime_start_failure_details(log_excerpt),
    }


def _launch_runtime_process(command: list[str], log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        return subprocess.Popen(
            command,
            stdout=handle,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )


def _wait_for_runtime_start_signal(
    base_url: str,
    process,
    *,
    timeout_seconds: float = _START_SERVER_READY_TIMEOUT_SECONDS,
    poll_interval_seconds: float = _START_SERVER_READY_POLL_INTERVAL_SECONDS,
    now_fn=time.monotonic,
    sleep_fn=time.sleep,
    health_probe=None,
) -> dict[str, object]:
    health_probe = health_probe or probe_server_health
    deadline = now_fn() + max(0.0, float(timeout_seconds))
    loading_seen_at: float | None = None
    while now_fn() < deadline:
        health_status = str(health_probe(base_url) or "")
        current_time = now_fn()
        if health_status == "ready":
            return {"state": "responding", "health": health_status}
        if health_status == "loading":
            if loading_seen_at is None:
                loading_seen_at = current_time
            elif (current_time - loading_seen_at) >= _START_SERVER_LOADING_STABILITY_SECONDS:
                return {"state": "responding", "health": health_status}
        else:
            loading_seen_at = None
        if getattr(process, "poll", lambda: None)() is not None:
            return {"state": "exited", "health": health_status}
        sleep_fn(poll_interval_seconds)
    health_status = str(health_probe(base_url) or "")
    if health_status == "ready":
        return {"state": "responding", "health": health_status}
    if health_status == "loading" and getattr(process, "poll", lambda: None)() is None:
        return {"state": "responding", "health": health_status}
    if getattr(process, "poll", lambda: None)() is not None:
        return {"state": "exited", "health": health_status}
    return {"state": "pending", "health": health_status}


def _read_runtime_log_excerpt(log_path: Path, *, max_chars: int = _START_SERVER_LOG_EXCERPT_CHARS) -> str:
    if not log_path.exists():
        return ""
    return log_path.read_text(encoding="utf-8", errors="replace")[-max_chars:].strip()


def _read_runtime_log_excerpt_after_exit(
    log_path: Path,
    *,
    prefer_pattern: re.Pattern[str] | None = None,
    timeout_seconds: float = _START_SERVER_EXIT_LOG_WAIT_SECONDS,
    poll_interval_seconds: float = _START_SERVER_EXIT_LOG_POLL_INTERVAL_SECONDS,
    now_fn=time.monotonic,
    sleep_fn=time.sleep,
) -> str:
    deadline = now_fn() + max(0.0, float(timeout_seconds))
    latest_excerpt = ""
    while True:
        latest_excerpt = _read_runtime_log_excerpt(log_path)
        if latest_excerpt:
            if prefer_pattern is None or prefer_pattern.search(latest_excerpt):
                return latest_excerpt
        if now_fn() >= deadline:
            return latest_excerpt
        sleep_fn(poll_interval_seconds)


def _should_retry_runtime_without_explicit_main_gpu(
    *,
    launch_arguments: dict[str, object],
    log_excerpt: str,
) -> bool:
    if not isinstance(launch_arguments, dict):
        return False
    if "main_gpu" not in launch_arguments and "split_mode" not in launch_arguments:
        return False
    return bool(_INVALID_MAIN_GPU_RE.search(str(log_excerpt or "")))


def _format_runtime_start_failure_details(log_excerpt: str) -> str:
    cleaned_excerpt = str(log_excerpt or "").strip()
    if cleaned_excerpt:
        return f"Log: {cleaned_excerpt}"
    return "Runtime proces je prerano završen pre nego što je health endpoint odgovorio."


def _build_runtime_live_signal(
    health_status: str,
    pid: int | None,
) -> tuple[str, str]:
    if health_status == "ready":
        return "started", "Runtime health endpoint odgovara."
    if health_status == "loading":
        return "warming", "Runtime odgovara, ali model se još učitava."
    if pid is not None:
        return "degraded", "Runtime proces postoji, ali health endpoint ne odgovara."
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
    return _resolve_runtime_context_size_for_runtime(
        config,
        runtime_state,
        str(runtime_state.get("active_runtime", "") or ""),
    )


def _resolve_runtime_context_size_for_runtime(
    config: ControlCenterConfig,
    runtime_state: dict[str, object],
    runtime_name: str,
) -> int | None:
    active_runtime = str(runtime_state.get("active_runtime", "") or "").strip().lower()
    normalized_runtime = str(runtime_name or active_runtime).strip().lower()
    if normalized_runtime == "turboquant":
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


def _positive_int_or_zero(value: object) -> int:
    parsed = _positive_int_or_none(value)
    return parsed if parsed is not None else 0


def _non_negative_int_or_none(value: object) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _resolve_spec_type(
    runtime_state: dict[str, object],
    binary_path: Path,
) -> str | None:
    return _resolve_spec_type_for_runtime(
        runtime_state,
        binary_path,
        str(runtime_state.get("active_runtime", "") or ""),
    )


def _resolve_spec_type_for_runtime(
    runtime_state: dict[str, object],
    binary_path: Path,
    runtime_name: str,
) -> str | None:
    normalized_runtime = str(runtime_name or "").strip().lower()
    if normalized_runtime != "llama.cpp":
        return None
    active_model_id = str(runtime_state.get("active_model_id", "") or "").lower()
    active_model_path = Path(str(runtime_state.get("active_model_path", "") or ""))
    joined = " ".join(
        part
        for part in [active_model_id, active_model_path.name.lower(), active_model_path.parent.name.lower()]
        if part
    )
    if "mtp" not in joined:
        return None
    try:
        supports_draft_mtp = runtime_supports_draft_mtp(binary_path)
    except OSError:
        supports_draft_mtp = False
    if not supports_draft_mtp:
        return None
    return "draft-mtp"


def _build_start_capability(runtime_state: dict[str, object]) -> tuple[bool, str]:
    binary_path = Path(str(runtime_state.get("active_binary", "") or ""))
    if not binary_path.is_file():
        return False, "Aktivni runtime binar nije pronađen."
    model_path = Path(str(runtime_state.get("active_model_path", "") or ""))
    if not model_path.is_file():
        return False, "Aktivni model nije pronađen."
    if not bool(runtime_state.get("active_model_supported", True)):
        return (
            False,
            str(runtime_state.get("active_model_reason", "") or "Aktivni model nije podržan za runtime start."),
        )
    return True, ""


def _stop_orphaned_runtime_processes(install_root: Path) -> bool:
    runtime_targets = [
        install_root / "runtime" / "llama.cpp" / "llama-server.exe",
        *sorted((install_root / "tools" / "turboquant").glob("**/llama-server.exe")),
    ]
    existing_targets = [path for path in runtime_targets if path.is_file()]
    if not existing_targets:
        return False

    target_list = ", ".join(_quote_powershell_string(str(path)) for path in existing_targets)
    powershell_command = (
        f"$targets = @({target_list}); "
        "$matches = Get-CimInstance Win32_Process | Where-Object { "
        "$_.ExecutablePath -and $targets -contains $_.ExecutablePath "
        "}; "
        "if (-not $matches) { exit 2 }; "
        "$matches | ForEach-Object { "
        "Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue "
        "};"
    )
    completed = subprocess.run(
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
    return completed.returncode == 0


def _quote_powershell_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _build_server_command_preview(
    config: ControlCenterConfig,
    runtime_state: dict[str, object],
) -> dict[str, object]:
    model_path = Path(str(runtime_state.get("active_model_path", "") or ""))
    active_runtime = str(runtime_state.get("active_runtime", "") or "").strip().lower() or "llama.cpp"
    variants = [
        _build_server_command_variant(
            config,
            runtime_state,
            runtime_name="llama.cpp",
            runtime_label="llama.cpp",
            binary_path=Path(str(runtime_state.get("llama_binary", "") or "")),
            runtime_available=bool(runtime_state.get("llama_available", False)),
            runtime_reason=str(runtime_state.get("llama_reason", "") or ""),
        ),
        _build_server_command_variant(
            config,
            runtime_state,
            runtime_name="turboquant",
            runtime_label="TurboQuant",
            binary_path=Path(str(runtime_state.get("turbo_binary", "") or "")),
            runtime_available=bool(runtime_state.get("turbo_available", False)),
            runtime_reason=str(runtime_state.get("turbo_reason", "") or ""),
        ),
    ]
    active_variant = next(
        (item for item in variants if item["runtime"] == active_runtime),
        variants[0],
    )
    return {
        "shellLabel": "PowerShell / cmd.exe",
        "activeRuntime": active_runtime,
        "activeRuntimeLabel": _runtime_label(active_runtime),
        "activeCommand": str(active_variant.get("command", "") or ""),
        "activeCmdCommand": str(active_variant.get("cmdCommand", "") or ""),
        "modelPath": str(model_path),
        "notes": [
            "Lokalni model se prosleđuje kroz --model argument.",
            "Isti runtime koristi isti port i isti --ctx-size koji vidiš ovde.",
            "PowerShell prikaz počinje sa & jer tako PowerShell pokreće citiranu .exe putanju.",
            "cmd.exe varijanta je odvojena i ne koristi & operator.",
            "llama.cpp sada pokušava i GPU offload kada je NVIDIA GPU dostupan, pa kroz komandu možeš da vidiš i --n-gpu-layers / --flash-attn.",
        ],
        "variants": variants,
    }


def _build_server_command_variant(
    config: ControlCenterConfig,
    runtime_state: dict[str, object],
    *,
    runtime_name: str,
    runtime_label: str,
    binary_path: Path,
    runtime_available: bool,
    runtime_reason: str,
) -> dict[str, object]:
    port = int(runtime_state.get("port", 0) or 0)
    model_id = str(runtime_state.get("active_model_id", "") or "")
    model_path = Path(str(runtime_state.get("active_model_path", "") or ""))
    context_size = _resolve_runtime_context_size_for_runtime(config, runtime_state, runtime_name)
    spec_type = _resolve_spec_type_for_runtime(runtime_state, binary_path, runtime_name)
    generation_arguments = _load_runtime_launch_argument_values(
        config,
        runtime_state,
        runtime_name=runtime_name,
        binary_path=binary_path,
    )
    command: list[str] = []
    summary = ""
    supported = False
    if not binary_path.is_file():
        summary = f"{runtime_label} binar nije pronađen u ovoj instalaciji."
    elif not model_path.is_file():
        summary = "Aktivni model nije pronađen, pa komanda nije potpuna."
    else:
        command = _build_server_command(
            ServerVerificationTarget(
                server_executable=binary_path,
                model_id=model_id,
                model_path=model_path,
                active_model_config_path=config.install_root / "config" / "active-model.json",
            ),
            port,
            ctx_size=context_size,
            spec_type=spec_type,
            **generation_arguments,
        )
        supported, support_reason = classify_runtime_model_support(
            model_id=model_id,
            model_path=model_path,
            runtime_name=runtime_name,
            runtime_binary_path=binary_path,
        )
        if not runtime_available:
            summary = runtime_reason or f"{runtime_label} trenutno ne prolazi launch proveru."
        elif not supported:
            summary = support_reason
        else:
            summary = f"Ovo je ekvivalentna komanda za {runtime_label} sa aktivnim modelom i trenutnim context podešavanjem."
    return {
        "runtime": runtime_name,
        "runtimeLabel": runtime_label,
        "available": runtime_available and supported and bool(command),
        "summary": summary,
        "binaryPath": str(binary_path),
        "modelPath": str(model_path),
        "context": context_size,
        "specType": spec_type or "",
        "samplingSummary": _build_generation_summary(generation_arguments),
        "launchSummary": _build_launch_summary(generation_arguments),
        "command": _format_powershell_command(command) if command else "",
        "cmdCommand": _format_cmd_command(command) if command else "",
    }


def load_runtime_diagnostics(
    *,
    runtime_name: str,
    launch_arguments: dict[str, object] | None,
    log_path: Path | None,
) -> dict[str, object]:
    requested_gpu_layers = _positive_int_or_zero((launch_arguments or {}).get("gpu_layers"))
    requested_flash_attention = str((launch_arguments or {}).get("flash_attn", "") or "").strip()
    requested_main_gpu = _non_negative_int_or_none((launch_arguments or {}).get("main_gpu"))
    requested_split_mode = str((launch_arguments or {}).get("split_mode", "") or "").strip()
    log_text = _read_runtime_log_text(log_path)
    backend = _detect_runtime_backend(log_text)
    device_label = _last_match_group(_DEVICE_LABEL_RE, log_text, "label")
    projected_device_memory_mib = _last_match_int(_PROJECTED_DEVICE_MEMORY_RE, log_text, "used")
    projected_host_memory_mib = _last_match_int(_PROJECTED_HOST_MEMORY_RE, log_text, "used")
    confirmed_gpu_layers = _last_match_int(_OFFLOADED_LAYERS_RE, log_text, "gpu")
    confirmed_total_layers = _last_match_int(_OFFLOADED_LAYERS_RE, log_text, "total")
    cpu_mapped_model_buffer_mib = _last_match_float(_CPU_MAPPED_MODEL_BUFFER_RE, log_text, "value")
    model_buffer_mib = _last_match_float(_MODEL_BUFFER_RE, log_text, "value")
    kv_buffer_mib = _sum_last_matching_line_block(_KV_BUFFER_RE, log_text, "value")
    compute_buffer_mib = _last_match_float(_COMPUTE_BUFFER_RE, log_text, "value")

    has_log_evidence = any(
        value is not None
        for value in (
            projected_device_memory_mib,
            projected_host_memory_mib,
            confirmed_gpu_layers,
            confirmed_total_layers,
            cpu_mapped_model_buffer_mib,
            model_buffer_mib,
            kv_buffer_mib,
            compute_buffer_mib,
        )
    ) or bool(backend or device_label)
    normalized_runtime = str(runtime_name or "").strip().lower()
    if confirmed_gpu_layers is not None or (backend == "CUDA" and has_log_evidence):
        status = "confirmed"
    elif requested_gpu_layers > 0 or requested_flash_attention:
        status = "requested"
    elif normalized_runtime in {"llama.cpp", "turboquant"}:
        status = "cpu-only" if log_text else "unknown"
    else:
        status = "unknown"

    requested_summary_bits: list[str] = []
    if requested_gpu_layers > 0:
        requested_summary_bits.append(f"--n-gpu-layers {requested_gpu_layers}")
    if requested_flash_attention:
        requested_summary_bits.append(f"--flash-attn {requested_flash_attention}")
    if requested_main_gpu is not None:
        requested_summary_bits.append(f"--main-gpu {requested_main_gpu}")
    if requested_split_mode:
        requested_summary_bits.append(f"--split-mode {requested_split_mode}")
    requested_summary = (
        "Launch komanda traži " + " i ".join(requested_summary_bits)
        if requested_summary_bits
        else "Launch komanda trenutno ne traži eksplicitni GPU offload."
    )

    confirmed_summary_bits: list[str] = []
    if backend:
        confirmed_summary_bits.append(f"backend {backend}")
    if device_label:
        confirmed_summary_bits.append(device_label)
    if confirmed_gpu_layers is not None and confirmed_total_layers is not None:
        confirmed_summary_bits.append(f"offload {confirmed_gpu_layers}/{confirmed_total_layers} slojeva")
    if cpu_mapped_model_buffer_mib is not None:
        confirmed_summary_bits.append(f"CPU mapped {cpu_mapped_model_buffer_mib:.2f} MiB")
    if model_buffer_mib is not None:
        confirmed_summary_bits.append(f"model buffer {model_buffer_mib:.2f} MiB")
    if kv_buffer_mib is not None:
        confirmed_summary_bits.append(f"KV buffer {kv_buffer_mib:.2f} MiB")
    if compute_buffer_mib is not None:
        confirmed_summary_bits.append(f"compute buffer {compute_buffer_mib:.2f} MiB")
    confirmed_summary = (
        "Runtime log potvrđuje " + " | ".join(confirmed_summary_bits)
        if confirmed_summary_bits
        else "Runtime log još nije dao čitljiv dokaz o GPU offload-u."
    )

    notes = [requested_summary, confirmed_summary]
    if status == "requested":
        notes.append(
            "Na Windows WDDM okruženju `nvidia-smi` ume da izgleda niže ili nepotpuno, pa je runtime log bolji dokaz od Task Manager prikaza."
        )
    if status == "confirmed":
        notes.append(
            "Ako Task Manager pokaže manje VRAM-a nego što očekuješ, prednost daj runtime log linijama za CUDA model/KV/compute buffer."
        )
    if normalized_runtime == "turboquant":
        notes.append(
            "TurboQuant koristi sopstveni binar, ali ista dijagnostika ovde proverava šta je launch tražio i šta je runtime log stvarno potvrdio."
        )

    if status == "confirmed":
        summary = "GPU offload je potvrđen kroz runtime log."
    elif status == "requested":
        summary = "Launch komanda traži GPU offload, ali runtime log ga još nije potvrdio."
    elif status == "cpu-only":
        summary = "GPU offload trenutno nije potvrđen i runtime verovatno radi CPU-only."
    else:
        summary = "Nema dovoljno signala za pouzdanu GPU offload dijagnostiku."

    execution_mode_id, execution_mode_label, execution_mode_summary = _classify_execution_mode(
        status=status,
        confirmed_gpu_layers=confirmed_gpu_layers,
        confirmed_total_layers=confirmed_total_layers,
        requested_gpu_layers=requested_gpu_layers,
    )

    return {
        "status": status,
        "backend": backend,
        "deviceLabel": device_label,
        "requestedGpuLayers": requested_gpu_layers,
        "requestedFlashAttention": requested_flash_attention,
        "requestedMainGpu": requested_main_gpu,
        "requestedSplitMode": requested_split_mode,
        "projectedDeviceMemoryMiB": projected_device_memory_mib,
        "projectedHostMemoryMiB": projected_host_memory_mib,
        "confirmedGpuLayers": confirmed_gpu_layers,
        "confirmedTotalLayers": confirmed_total_layers,
        "cpuMappedModelBufferMiB": cpu_mapped_model_buffer_mib,
        "modelBufferMiB": model_buffer_mib,
        "kvBufferMiB": kv_buffer_mib,
        "computeBufferMiB": compute_buffer_mib,
        "executionModeId": execution_mode_id,
        "executionModeLabel": execution_mode_label,
        "executionModeSummary": execution_mode_summary,
        "requestedSummary": requested_summary,
        "confirmedSummary": confirmed_summary,
        "summary": summary,
        "notes": notes,
    }


def _attach_runtime_context_alignment(
    runtime_diagnostics: dict[str, object],
    *,
    config: ControlCenterConfig,
    runtime_state: dict[str, object],
    runtime_name: str,
    runtime_pid: int | None,
) -> dict[str, object]:
    payload = dict(runtime_diagnostics)
    configured_context = _resolve_runtime_context_size_for_runtime(config, runtime_state, runtime_name)
    effective_process_context = _read_runtime_process_context_size(runtime_pid)

    context_alignment_label = "Čeka živ proces"
    context_alignment_summary = "Config vrednost postoji, ali živi proces još nije potvrđen."
    context_mismatch = False

    if configured_context is not None and effective_process_context is not None:
        if configured_context == effective_process_context:
            context_alignment_label = "Config i živi proces su usklađeni"
            context_alignment_summary = (
                f"Config traži {configured_context}, a živi proces stvarno radi sa {effective_process_context}."
            )
        else:
            context_mismatch = True
            context_alignment_label = "Potreban restart runtime-a"
            context_alignment_summary = (
                f"Config traži {configured_context}, a živi proces i dalje radi sa {effective_process_context}. "
                "Sačuvane promene neće važiti dok ne restartuješ runtime."
            )
    elif configured_context is not None:
        context_alignment_label = "Čeka živ proces"
        context_alignment_summary = (
            f"Config traži {configured_context}, ali živi proces još nije potvrđen pa efektivni ctx-size nije poznat."
        )
    elif effective_process_context is not None:
        context_alignment_label = "Živi proces bez config reference"
        context_alignment_summary = (
            f"Živi proces radi sa {effective_process_context}, ali config vrednost trenutno nije dostupna."
        )

    payload["configuredContext"] = configured_context
    payload["effectiveProcessContext"] = effective_process_context
    payload["contextMismatch"] = context_mismatch
    payload["contextAlignmentLabel"] = context_alignment_label
    payload["contextAlignmentSummary"] = context_alignment_summary

    notes = list(payload.get("notes", []))
    if context_alignment_summary and context_alignment_summary not in notes:
        notes.append(context_alignment_summary)
    payload["notes"] = notes
    return payload


def _read_runtime_process_context_size(runtime_pid: int | None) -> int | None:
    command_line = _read_runtime_process_command_line(runtime_pid)
    if not command_line:
        return None
    match = _CTX_SIZE_FLAG_RE.search(command_line)
    if not match:
        return None
    try:
        return int(match.group("value"))
    except (TypeError, ValueError):
        return None


def _read_runtime_process_command_line(runtime_pid: int | None) -> str:
    if not isinstance(runtime_pid, int) or runtime_pid <= 0:
        return ""
    if os.name != "nt":
        return ""
    now = time.monotonic()
    with _RUNTIME_PROCESS_COMMAND_LINE_CACHE_LOCK:
        cached_payload = _RUNTIME_PROCESS_COMMAND_LINE_CACHE.get(runtime_pid)
        if cached_payload is not None:
            cached_at, cached_command_line = cached_payload
            if (now - cached_at) <= RUNTIME_PROCESS_COMMAND_LINE_CACHE_TTL_SECONDS:
                return cached_command_line
    powershell_command = (
        f"$proc = Get-CimInstance Win32_Process -Filter \"ProcessId = {runtime_pid}\"; "
        "if ($proc) { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $proc.CommandLine }"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", powershell_command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if completed.returncode != 0:
        return ""
    command_line = str(completed.stdout or "").strip()
    with _RUNTIME_PROCESS_COMMAND_LINE_CACHE_LOCK:
        _RUNTIME_PROCESS_COMMAND_LINE_CACHE[runtime_pid] = (time.monotonic(), command_line)
    return command_line


def _format_powershell_command(command: list[str]) -> str:
    if not command:
        return ""
    rendered = [f"& {_quote_powershell_argument(command[0])}"]
    rendered.extend(_quote_powershell_argument(item) for item in command[1:])
    return " ".join(rendered)


def _format_cmd_command(command: list[str]) -> str:
    if not command:
        return ""
    rendered = [_quote_cmd_argument(command[0])]
    rendered.extend(_quote_cmd_argument(item) for item in command[1:])
    return " ".join(rendered)


def _quote_powershell_argument(value: str) -> str:
    if _POWERSHELL_SAFE_ARGUMENT_RE.fullmatch(value):
        return value
    escaped = value.replace('"', '`"')
    return f'"{escaped}"'


def _quote_cmd_argument(value: str) -> str:
    if _POWERSHELL_SAFE_ARGUMENT_RE.fullmatch(value):
        return value
    escaped = value.replace('"', '\\"')
    return f'"{escaped}"'


def _load_generation_argument_values(
    config: ControlCenterConfig,
) -> dict[str, object]:
    settings = load_effective_settings_state(config)
    return {
        "temperature": float(settings.get("temperature", 0.8)),
        "top_k": int(settings.get("topK", 40)),
        "top_p": float(settings.get("topP", 0.95)),
        "min_p": float(settings.get("minP", 0.05)),
        "repeat_penalty": float(settings.get("repeatPenalty", 1.0)),
        "repeat_last_n": int(settings.get("repeatLastN", 64)),
        "presence_penalty": float(settings.get("presencePenalty", 0.0)),
        "frequency_penalty": float(settings.get("frequencyPenalty", 0.0)),
        "seed": int(settings.get("seed", -1)),
    }


def _load_runtime_launch_argument_values(
    config: ControlCenterConfig,
    runtime_state: dict[str, object],
    *,
    runtime_name: str,
    binary_path: Path,
) -> dict[str, object]:
    arguments = _load_generation_argument_values(config)
    arguments.update(
        _load_runtime_acceleration_argument_values(
            config,
            runtime_state,
            runtime_name=runtime_name,
            binary_path=binary_path,
        )
    )
    arguments.update(
        _load_runtime_capacity_argument_values(
            config,
            runtime_name=runtime_name,
            binary_path=binary_path,
        )
    )
    return arguments


def _load_runtime_acceleration_argument_values(
    config: ControlCenterConfig,
    runtime_state: dict[str, object],
    *,
    runtime_name: str,
    binary_path: Path,
) -> dict[str, object]:
    del runtime_state
    normalized_runtime = str(runtime_name or "").strip().lower()
    if normalized_runtime not in {"llama.cpp", "turboquant"}:
        return {}
    if not _runtime_binary_supports_flag(binary_path, "--n-gpu-layers"):
        return {}
    gpu_inventory = _detect_nvidia_gpu_inventory()
    preferred_gpu = _select_preferred_gpu(gpu_inventory)
    gpu_total_mib = (
        int(preferred_gpu.get("totalMemoryMiB", 0) or 0)
        if preferred_gpu is not None
        else _detect_nvidia_total_memory_mib()
    )
    effective_settings = load_effective_settings_state(config)
    gpu_layers_mode = str(effective_settings.get("gpuLayersMode", "auto") or "auto").strip().lower()
    manual_gpu_layers = _positive_int_or_zero(effective_settings.get("gpuLayersOverride"))
    gpu_layers = (
        manual_gpu_layers
        if gpu_layers_mode == "manual" and manual_gpu_layers > 0
        else _recommend_gpu_layers(gpu_total_mib)
    )
    if gpu_layers <= 0:
        return {}
    acceleration: dict[str, object] = {"gpu_layers": gpu_layers}
    if _runtime_binary_supports_flag(binary_path, "--flash-attn"):
        acceleration["flash_attn"] = "auto"
    if preferred_gpu is not None:
        if _runtime_binary_supports_flag(binary_path, "--main-gpu"):
            acceleration["main_gpu"] = int(preferred_gpu.get("index", 0) or 0)
        if _runtime_binary_supports_flag(binary_path, "--split-mode"):
            acceleration["split_mode"] = "none"
    return acceleration


def _load_runtime_capacity_argument_values(
    config: ControlCenterConfig,
    *,
    runtime_name: str,
    binary_path: Path,
) -> dict[str, object]:
    if not _runtime_binary_supports_flag(binary_path, "--parallel"):
        return {}
    normalized_runtime = str(runtime_name or "").strip().lower()
    gpu_inventory = _detect_nvidia_gpu_inventory()
    preferred_gpu = _select_preferred_gpu(gpu_inventory)
    gpu_total_mib = (
        int(preferred_gpu.get("totalMemoryMiB", 0) or 0)
        if preferred_gpu is not None
        else _detect_nvidia_total_memory_mib()
    )
    effective_settings = load_effective_settings_state(config)
    configured_context = _positive_int_or_zero(
        load_turboquant_config(config).get("context")
        if normalized_runtime == "turboquant"
        else effective_settings.get("context"),
    )
    if gpu_total_mib > 0 and gpu_total_mib <= 16 * 1024 and configured_context >= 65536:
        return {"parallel": 1}
    return {}


def _build_launch_summary(arguments: dict[str, object]) -> str:
    details: list[str] = []
    parallel = arguments.get("parallel")
    if isinstance(parallel, int) and parallel > 0:
        details.append(f"parallel {parallel}")
    gpu_layers = arguments.get("gpu_layers")
    if isinstance(gpu_layers, int) and gpu_layers > 0:
        details.append(f"GPU offload {gpu_layers} slojeva")
    flash_attn = str(arguments.get("flash_attn", "") or "").strip()
    if flash_attn:
        details.append(f"flash-attn {flash_attn}")
    main_gpu = arguments.get("main_gpu")
    if isinstance(main_gpu, int) and main_gpu >= 0:
        details.append(f"glavni GPU {main_gpu}")
    split_mode = str(arguments.get("split_mode", "") or "").strip()
    if split_mode:
        details.append(f"split-mode {split_mode}")
    batch_size = arguments.get("batch_size")
    if isinstance(batch_size, int) and batch_size > 0:
        details.append(f"batch {batch_size}")
    ubatch_size = arguments.get("ubatch_size")
    if isinstance(ubatch_size, int) and ubatch_size > 0:
        details.append(f"ubatch {ubatch_size}")
    return " | ".join(details)


def _build_generation_summary(arguments: dict[str, object]) -> str:
    return (
        f"temp {arguments['temperature']} | top-k {arguments['top_k']} | "
        f"top-p {arguments['top_p']} | min-p {arguments['min_p']} | "
        f"repeat {arguments['repeat_penalty']} / last-n {arguments['repeat_last_n']} | "
        f"presence {arguments['presence_penalty']} | frequency {arguments['frequency_penalty']} | "
        f"seed {arguments['seed']}"
    )


def _read_runtime_log_text(log_path: Path | None) -> str:
    if log_path is None:
        return ""
    resolved = Path(str(log_path))
    try:
        return resolved.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _detect_runtime_backend(log_text: str) -> str:
    lowered = log_text.lower()
    if "ggml_cuda_init" in lowered or "cuda0" in lowered:
        return "CUDA"
    if "ggml_vulkan_init" in lowered:
        return "Vulkan"
    if "metal" in lowered:
        return "Metal"
    if "sycl" in lowered:
        return "SYCL"
    return ""


def _last_match_group(pattern: re.Pattern[str], text: str, group: str) -> str:
    matches = list(pattern.finditer(text))
    if not matches:
        return ""
    return str(matches[-1].group(group) or "").strip()


def _last_match_int(pattern: re.Pattern[str], text: str, group: str) -> int | None:
    matches = list(pattern.finditer(text))
    if not matches:
        return None
    try:
        return int(matches[-1].group(group))
    except (TypeError, ValueError):
        return None


def _last_match_float(pattern: re.Pattern[str], text: str, group: str) -> float | None:
    matches = list(pattern.finditer(text))
    if not matches:
        return None
    try:
        return float(matches[-1].group(group))
    except (TypeError, ValueError):
        return None


def _sum_last_matching_line_block(pattern: re.Pattern[str], text: str, group: str) -> float | None:
    current_block: list[float] = []
    last_block: list[float] = []
    for line in (text or "").splitlines():
        match = pattern.search(line)
        if not match:
            if current_block:
                last_block = current_block
                current_block = []
            continue
        try:
            current_block.append(float(match.group(group)))
        except (TypeError, ValueError):
            continue
    if current_block:
        last_block = current_block
    return sum(last_block) if last_block else None


def _runtime_binary_supports_flag(binary_path: Path, flag: str) -> bool:
    resolved = Path(str(binary_path or ""))
    if not resolved.is_file() or not flag.strip():
        return False
    try:
        stat = resolved.stat()
    except OSError:
        return False
    output = _load_runtime_binary_help_output(str(resolved), stat.st_mtime_ns, stat.st_size)
    return flag in output


@lru_cache(maxsize=16)
def _load_runtime_binary_help_output(
    binary_path: str,
    modified_at_ns: int,
    size_bytes: int,
) -> str:
    del modified_at_ns, size_bytes
    try:
        completed = subprocess.run(
            [binary_path, "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, TypeError, ValueError):
        return ""
    if completed.returncode != 0:
        return ""
    return f"{completed.stdout}\n{completed.stderr}"


def _detect_nvidia_gpu_inventory() -> list[dict[str, object]]:
    completed = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=index,name,memory.total,memory.used,utilization.gpu",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode != 0:
            return []

    devices: list[dict[str, object]] = []
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 4:
            continue
        try:
            index = int(float(parts[0]))
            total_memory_mib = int(float(parts[2]))
            used_memory_mib = int(float(parts[3]))
        except ValueError:
            continue
        utilization_gpu_percent: float | None = None
        if len(parts) >= 5:
            try:
                utilization_gpu_percent = float(parts[4])
            except ValueError:
                utilization_gpu_percent = None
        devices.append(
            {
                "index": index,
                "name": parts[1],
                "totalMemoryMiB": total_memory_mib,
                "usedMemoryMiB": used_memory_mib,
                "freeMemoryMiB": max(total_memory_mib - used_memory_mib, 0),
                "utilizationGpuPercent": utilization_gpu_percent,
            }
        )
    return devices


def _select_preferred_gpu(devices: list[dict[str, object]]) -> dict[str, object] | None:
    normalized_devices = [device for device in devices if isinstance(device, dict)]
    if not normalized_devices:
        return None
    return max(
        normalized_devices,
        key=lambda item: (
            int(item.get("totalMemoryMiB", 0) or 0),
            int(item.get("freeMemoryMiB", 0) or 0),
            -int(item.get("index", 0) or 0),
        ),
    )


def _detect_nvidia_total_memory_mib() -> int | None:
    preferred_gpu = _select_preferred_gpu(_detect_nvidia_gpu_inventory())
    if preferred_gpu is None:
        return None
    try:
        return int(preferred_gpu.get("totalMemoryMiB", 0) or 0)
    except (TypeError, ValueError):
        return None


def _recommend_gpu_layers(total_memory_mib: int | None) -> int:
    if total_memory_mib is None or total_memory_mib <= 0:
        return 0
    if total_memory_mib >= 24 * 1024:
        return 99
    if total_memory_mib >= 16 * 1024:
        return 60
    if total_memory_mib >= 12 * 1024:
        return 40
    if total_memory_mib >= 8 * 1024:
        return 28
    if total_memory_mib >= 6 * 1024:
        return 20
    return 0


def _classify_execution_mode(
    *,
    status: str,
    confirmed_gpu_layers: int | None,
    confirmed_total_layers: int | None,
    requested_gpu_layers: int,
) -> tuple[str, str, str]:
    confirmed_gpu_layers = confirmed_gpu_layers or 0
    confirmed_total_layers = confirmed_total_layers or 0
    if status == "confirmed" and confirmed_total_layers > 0 and confirmed_gpu_layers >= confirmed_total_layers:
        return (
            "gpu-vram",
            "GPU VRAM dominantno",
            "Svi slojevi su potvrđeni na GPU-u. Host RAM se i dalje koristi za mapiranje i radne bafere.",
        )
    if (status == "confirmed" and confirmed_gpu_layers > 0) or (status == "requested" and requested_gpu_layers > 0):
        return (
            "hybrid-vram-ram",
            "Hibrid VRAM + RAM",
            "GPU je uključen u izvršavanje, ali model ili dalje koristi i sistemski RAM.",
        )
    if status == "cpu-only":
        return (
            "cpu-ram",
            "CPU + RAM",
            "Runtime trenutno nema potvrđen GPU offload i model radi preko CPU-a i sistemskog RAM-a.",
        )
    return (
        "unknown",
        "Čeka potvrdu",
        "Nema dovoljno živih signala da se sigurno klasifikuje gde model trenutno radi.",
    )
