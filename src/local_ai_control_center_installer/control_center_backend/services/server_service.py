from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
import re
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
_POWERSHELL_SAFE_ARGUMENT_RE = re.compile(r"^[A-Za-z0-9_./:-]+$")
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
_KV_BUFFER_RE = re.compile(
    r"KV buffer size =\s+(?P<value>\d+(?:\.\d+)?) MiB",
    re.IGNORECASE,
)
_COMPUTE_BUFFER_RE = re.compile(
    r"compute buffer size =\s+(?P<value>\d+(?:\.\d+)?) MiB",
    re.IGNORECASE,
)


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

    command = _build_server_command(
        ServerVerificationTarget(
            server_executable=binary_path,
            model_id=str(runtime_state["active_model_id"]),
            model_path=model_path,
            active_model_config_path=config.install_root / "config" / "active-model.json",
        ),
        port,
        ctx_size=_resolve_runtime_context_size(config, runtime_state),
        spec_type=_resolve_spec_type(runtime_state, binary_path),
        **_load_runtime_launch_argument_values(
            config,
            runtime_state,
            runtime_name=str(runtime_state.get("active_runtime", "") or ""),
            binary_path=binary_path,
        ),
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
        restart_summary,
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
    log_text = _read_runtime_log_text(log_path)
    backend = _detect_runtime_backend(log_text)
    device_label = _last_match_group(_DEVICE_LABEL_RE, log_text, "label")
    projected_device_memory_mib = _last_match_int(_PROJECTED_DEVICE_MEMORY_RE, log_text, "used")
    projected_host_memory_mib = _last_match_int(_PROJECTED_HOST_MEMORY_RE, log_text, "used")
    confirmed_gpu_layers = _last_match_int(_OFFLOADED_LAYERS_RE, log_text, "gpu")
    confirmed_total_layers = _last_match_int(_OFFLOADED_LAYERS_RE, log_text, "total")
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

    return {
        "status": status,
        "backend": backend,
        "deviceLabel": device_label,
        "requestedGpuLayers": requested_gpu_layers,
        "requestedFlashAttention": requested_flash_attention,
        "projectedDeviceMemoryMiB": projected_device_memory_mib,
        "projectedHostMemoryMiB": projected_host_memory_mib,
        "confirmedGpuLayers": confirmed_gpu_layers,
        "confirmedTotalLayers": confirmed_total_layers,
        "modelBufferMiB": model_buffer_mib,
        "kvBufferMiB": kv_buffer_mib,
        "computeBufferMiB": compute_buffer_mib,
        "requestedSummary": requested_summary,
        "confirmedSummary": confirmed_summary,
        "summary": summary,
        "notes": notes,
    }


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
    return arguments


def _load_runtime_acceleration_argument_values(
    config: ControlCenterConfig,
    runtime_state: dict[str, object],
    *,
    runtime_name: str,
    binary_path: Path,
) -> dict[str, object]:
    del config
    del runtime_state
    normalized_runtime = str(runtime_name or "").strip().lower()
    if normalized_runtime != "llama.cpp":
        return {}
    if not _runtime_binary_supports_flag(binary_path, "--n-gpu-layers"):
        return {}
    gpu_total_mib = _detect_nvidia_total_memory_mib()
    gpu_layers = _recommend_gpu_layers(gpu_total_mib)
    if gpu_layers <= 0:
        return {}
    acceleration: dict[str, object] = {"gpu_layers": gpu_layers}
    if _runtime_binary_supports_flag(binary_path, "--flash-attn"):
        acceleration["flash_attn"] = "auto"
    return acceleration


def _build_launch_summary(arguments: dict[str, object]) -> str:
    details: list[str] = []
    gpu_layers = arguments.get("gpu_layers")
    if isinstance(gpu_layers, int) and gpu_layers > 0:
        details.append(f"GPU offload {gpu_layers} slojeva")
    flash_attn = str(arguments.get("flash_attn", "") or "").strip()
    if flash_attn:
        details.append(f"flash-attn {flash_attn}")
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


@lru_cache(maxsize=16)
def _runtime_binary_supports_flag(binary_path: Path, flag: str) -> bool:
    resolved = Path(str(binary_path or ""))
    if not resolved.is_file() or not flag.strip():
        return False
    try:
        completed = subprocess.run(
            [str(resolved), "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, TypeError, ValueError):
        return False
    if completed.returncode != 0:
        return False
    output = f"{completed.stdout}\n{completed.stderr}"
    return flag in output


def _detect_nvidia_total_memory_mib() -> int | None:
    completed = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0:
        return None
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            return int(float(line))
        except ValueError:
            continue
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
