from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import platform
import socket
import subprocess
import threading
import time
from typing import Any

from local_ai_control_center_installer.control_center_backend.config import (
    ControlCenterConfig,
    get_config,
)
from local_ai_control_center_installer.control_center_backend.services.benchmark_service import (
    load_benchmark_summary,
)
from local_ai_control_center_installer.control_center_backend.services.server_service import (
    _attach_runtime_context_alignment,
    _detect_nvidia_gpu_inventory,
    _load_runtime_launch_argument_values,
    _select_preferred_gpu,
    load_runtime_diagnostics,
)
from local_ai_control_center_installer.control_center_backend.services.compatibility_service import (
    detect_ram_gib,
    detect_vram_gib,
)
from local_ai_control_center_installer.control_center_backend.services.status_service import (
    find_runtime_pid,
    load_runtime_state,
)

OBSERVABILITY_CACHE_TTL_SECONDS = 5.0
RUNTIME_RESOURCE_SNAPSHOT_CACHE_TTL_SECONDS = 15.0
SYSTEM_SNAPSHOT_CACHE_TTL_SECONDS = 15.0
WINDOWS_SYSTEM_METRICS_CACHE_TTL_SECONDS = 5.0
PROCESS_WORKING_SET_CACHE_TTL_SECONDS = 5.0
_OBSERVABILITY_CACHE_LOCK = threading.Lock()
_OBSERVABILITY_PAYLOAD_CACHE: dict[str, tuple[float, tuple[tuple[str, int | None, int | None], ...], dict[str, Any]]] = {}
_OBSERVABILITY_PAYLOAD_INFLIGHT: dict[
    str,
    tuple[threading.Event, tuple[tuple[str, int | None, int | None], ...]],
] = {}
_RUNTIME_RESOURCE_SNAPSHOT_CACHE_LOCK = threading.Lock()
_RUNTIME_RESOURCE_SNAPSHOT_CACHE: dict[
    str,
    tuple[float, tuple[tuple[str, int | None, int | None], ...], dict[str, Any]],
] = {}
_RUNTIME_RESOURCE_SNAPSHOT_INFLIGHT: dict[
    str,
    tuple[threading.Event, tuple[tuple[str, int | None, int | None], ...]],
] = {}
_SYSTEM_SNAPSHOT_CACHE_LOCK = threading.Lock()
_SYSTEM_SNAPSHOT_CACHE: dict[
    str,
    tuple[float, tuple[tuple[str, int | None, int | None], ...], dict[str, Any]],
] = {}
_SYSTEM_SNAPSHOT_INFLIGHT: dict[
    str,
    tuple[threading.Event, tuple[tuple[str, int | None, int | None], ...]],
] = {}
_WINDOWS_SYSTEM_METRICS_CACHE: tuple[float, dict[str, float | None]] | None = None
_PROCESS_WORKING_SET_CACHE_LOCK = threading.Lock()
_PROCESS_WORKING_SET_CACHE: dict[int, tuple[float, float | None]] = {}


def load_observability_payload(
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    config = config or get_config()
    cache_scope = str(config.install_root)
    while True:
        cache_signature = _build_observability_cache_signature(config)
        now = time.monotonic()
        with _OBSERVABILITY_CACHE_LOCK:
            cached_payload = _OBSERVABILITY_PAYLOAD_CACHE.get(cache_scope)
            if cached_payload is not None:
                cached_at, cached_signature, payload = cached_payload
                if cached_signature == cache_signature and (now - cached_at) <= OBSERVABILITY_CACHE_TTL_SECONDS:
                    return payload

            inflight_payload = _OBSERVABILITY_PAYLOAD_INFLIGHT.get(cache_scope)
            if inflight_payload is None or inflight_payload[1] != cache_signature:
                wait_event = threading.Event()
                _OBSERVABILITY_PAYLOAD_INFLIGHT[cache_scope] = (wait_event, cache_signature)
                owns_compute = True
            else:
                wait_event = inflight_payload[0]
                owns_compute = False

        if owns_compute:
            break

        wait_event.wait(timeout=max(OBSERVABILITY_CACHE_TTL_SECONDS, 0.5) + 15.0)

    payload: dict[str, Any] | None = None
    try:
        runtime_state = load_runtime_state(config)
        runtime_snapshot = load_runtime_resource_snapshot(config, runtime_state)
        benchmark_summary = load_benchmark_summary(config)
        telemetry = dict(benchmark_summary.get("telemetry", {}) or {})
        activity = dict(benchmark_summary.get("activity", {}) or {})

        payload = {
            "generatedAt": _utc_now(),
            "system": load_system_snapshot(
                config,
                selected_gpu_index=runtime_snapshot.get("selectedGpuIndex"),
            ),
            "runtime": runtime_snapshot,
            "telemetry": {
                "input24h": _coerce_int(telemetry.get("input24hTokens", telemetry.get("input24h"))) or 0,
                "output24h": _coerce_int(telemetry.get("output24hTokens", telemetry.get("output24h"))) or 0,
                "total24h": _coerce_int(telemetry.get("total24hTokens", telemetry.get("total24h"))) or 0,
                "cost24hUsd": _coerce_float(
                    telemetry.get("estimatedCost24hUsd", telemetry.get("cost24hUsd"))
                )
                or 0.0,
                "activeRoutes": _coerce_int(telemetry.get("activeRoutes")) or 0,
                "activeRoutesLabel": str(telemetry.get("activeRoutesLabel", "") or "--"),
                "liveNowTokensPerSecond": _coerce_float(telemetry.get("liveNowTokensPerSecond")),
                "flowStateLabel": str(telemetry.get("flowStateLabel", "") or "idle"),
                "flowStateReason": str(telemetry.get("flowStateReason", "") or ""),
                "lastUpdatedAt": str(telemetry.get("lastUpdatedAt", telemetry.get("lastUpdate", "")) or ""),
                "promptSharePercent": _coerce_float(
                    telemetry.get("promptSharePercent", telemetry.get("inputSharePercent"))
                )
                or 0.0,
                "completionSharePercent": _coerce_float(
                    telemetry.get("completionSharePercent", telemetry.get("outputSharePercent"))
                )
                or 0.0,
                "launchQueueSignal": {
                    "label": str((telemetry.get("launchQueueSignal") or {}).get("label", "") or "quiet"),
                    "summary": str((telemetry.get("launchQueueSignal") or {}).get("summary", "") or ""),
                },
            },
            "activity": {
                "requestCount": _coerce_int(benchmark_summary.get("requestCount")) or 0,
                "averageTotalMs": _coerce_float(activity.get("averageTotalMs")),
                "lastMeasuredAt": benchmark_summary.get("lastMeasuredAt"),
                "stability": {
                    "label": str((activity.get("stability") or {}).get("label", "") or "--"),
                    "score": _coerce_int((activity.get("stability") or {}).get("score")) or 0,
                    "reason": str((activity.get("stability") or {}).get("reason", "") or ""),
                },
            },
            "logSignals": _load_recent_log_signals(config),
        }
        return payload
    finally:
        with _OBSERVABILITY_CACHE_LOCK:
            if payload is not None:
                stored_signature = _build_observability_cache_signature(config)
                _OBSERVABILITY_PAYLOAD_CACHE[cache_scope] = (time.monotonic(), stored_signature, payload)
            inflight_payload = _OBSERVABILITY_PAYLOAD_INFLIGHT.get(cache_scope)
            if inflight_payload is not None and inflight_payload[0] is wait_event:
                del _OBSERVABILITY_PAYLOAD_INFLIGHT[cache_scope]
                wait_event.set()


def load_runtime_resource_snapshot(
    config: ControlCenterConfig,
    runtime_state: dict[str, Any],
) -> dict[str, Any]:
    cache_scope = str(config.install_root)
    while True:
        cache_signature = _build_runtime_resource_snapshot_cache_signature(config, runtime_state)
        now = time.monotonic()
        with _RUNTIME_RESOURCE_SNAPSHOT_CACHE_LOCK:
            cached_payload = _RUNTIME_RESOURCE_SNAPSHOT_CACHE.get(cache_scope)
            if cached_payload is not None:
                cached_at, cached_signature, payload = cached_payload
                if cached_signature == cache_signature and (now - cached_at) <= RUNTIME_RESOURCE_SNAPSHOT_CACHE_TTL_SECONDS:
                    return payload

            inflight_payload = _RUNTIME_RESOURCE_SNAPSHOT_INFLIGHT.get(cache_scope)
            if inflight_payload is None or inflight_payload[1] != cache_signature:
                wait_event = threading.Event()
                _RUNTIME_RESOURCE_SNAPSHOT_INFLIGHT[cache_scope] = (wait_event, cache_signature)
                owns_compute = True
            else:
                wait_event = inflight_payload[0]
                owns_compute = False

        if owns_compute:
            break

        wait_event.wait(timeout=max(RUNTIME_RESOURCE_SNAPSHOT_CACHE_TTL_SECONDS, 0.5) + 15.0)

    payload: dict[str, Any] | None = None
    try:
        payload = _build_runtime_resource_snapshot(config, runtime_state)
        return payload
    finally:
        with _RUNTIME_RESOURCE_SNAPSHOT_CACHE_LOCK:
            if payload is not None:
                stored_signature = _build_runtime_resource_snapshot_cache_signature(
                    config,
                    runtime_state,
                )
                _RUNTIME_RESOURCE_SNAPSHOT_CACHE[cache_scope] = (
                    time.monotonic(),
                    stored_signature,
                    payload,
                )
            inflight_payload = _RUNTIME_RESOURCE_SNAPSHOT_INFLIGHT.get(cache_scope)
            if inflight_payload is not None and inflight_payload[0] is wait_event:
                del _RUNTIME_RESOURCE_SNAPSHOT_INFLIGHT[cache_scope]
                wait_event.set()


def load_system_snapshot(
    config: ControlCenterConfig,
    *,
    selected_gpu_index: object = None,
) -> dict[str, Any]:
    cache_scope = str(config.install_root)
    while True:
        cache_signature = _build_system_snapshot_cache_signature(selected_gpu_index)
        now = time.monotonic()
        with _SYSTEM_SNAPSHOT_CACHE_LOCK:
            cached_payload = _SYSTEM_SNAPSHOT_CACHE.get(cache_scope)
            if cached_payload is not None:
                cached_at, cached_signature, payload = cached_payload
                if cached_signature == cache_signature and (now - cached_at) <= SYSTEM_SNAPSHOT_CACHE_TTL_SECONDS:
                    return payload

            inflight_payload = _SYSTEM_SNAPSHOT_INFLIGHT.get(cache_scope)
            if inflight_payload is None or inflight_payload[1] != cache_signature:
                wait_event = threading.Event()
                _SYSTEM_SNAPSHOT_INFLIGHT[cache_scope] = (wait_event, cache_signature)
                owns_compute = True
            else:
                wait_event = inflight_payload[0]
                owns_compute = False

        if owns_compute:
            break

        wait_event.wait(timeout=max(SYSTEM_SNAPSHOT_CACHE_TTL_SECONDS, 0.5) + 15.0)

    payload: dict[str, Any] | None = None
    try:
        payload = _detect_system_snapshot(config, selected_gpu_index=selected_gpu_index)
        return payload
    finally:
        with _SYSTEM_SNAPSHOT_CACHE_LOCK:
            if payload is not None:
                stored_signature = _build_system_snapshot_cache_signature(selected_gpu_index)
                _SYSTEM_SNAPSHOT_CACHE[cache_scope] = (
                    time.monotonic(),
                    stored_signature,
                    payload,
                )
            inflight_payload = _SYSTEM_SNAPSHOT_INFLIGHT.get(cache_scope)
            if inflight_payload is not None and inflight_payload[0] is wait_event:
                del _SYSTEM_SNAPSHOT_INFLIGHT[cache_scope]
                wait_event.set()


def _build_observability_cache_signature(
    config: ControlCenterConfig,
) -> tuple[tuple[str, int | None, int | None], ...]:
    runtime_selection_path = config.control_center_config_root / "runtime-selection.json"
    watched_paths = (
        config.active_model_config_path,
        config.runtime_endpoint_config_path,
        config.settings_path,
        config.turboquant_config_path,
        runtime_selection_path,
    )
    return tuple(_path_signature(path) for path in watched_paths)


def _build_runtime_resource_snapshot_cache_signature(
    config: ControlCenterConfig,
    runtime_state: dict[str, Any],
) -> tuple[tuple[str, int | None, int | None], ...]:
    runtime_selection_path = config.control_center_config_root / "runtime-selection.json"
    watched_paths = (
        config.active_model_config_path,
        config.runtime_endpoint_config_path,
        config.settings_path,
        config.turboquant_config_path,
        runtime_selection_path,
        config.install_root / "logs" / "runtime-server.log",
    )
    signature = list(_path_signature(path) for path in watched_paths)
    signature.extend(
        [
            ("active_runtime", None, hash(str(runtime_state.get("active_runtime", "") or ""))),
            ("active_model", None, hash(str(runtime_state.get("active_model", "") or ""))),
            ("active_binary", None, hash(str(runtime_state.get("active_binary", "") or ""))),
            ("runtime_live_status", None, hash(str(runtime_state.get("runtime_live_status", "") or ""))),
            ("port", None, _coerce_int(runtime_state.get("port"))),
        ]
    )
    return tuple(signature)


def _build_system_snapshot_cache_signature(
    selected_gpu_index: object,
) -> tuple[tuple[str, int | None, int | None], ...]:
    return (("selected_gpu_index", _coerce_int(selected_gpu_index), None),)


def _path_signature(path: Path) -> tuple[str, int | None, int | None]:
    resolved = Path(str(path))
    try:
        stat = resolved.stat()
    except OSError:
        return (str(resolved), None, None)
    return (str(resolved), stat.st_mtime_ns, stat.st_size)


def _detect_system_snapshot(
    config: ControlCenterConfig | None = None,
    *,
    selected_gpu_index: object = None,
) -> dict[str, Any]:
    del config
    platform_label = {
        "Windows": "Windows",
        "Linux": "Linux",
        "Darwin": "macOS",
    }.get(platform.system(), platform.system() or "Unknown")
    ram_total = detect_ram_gib()
    ram_used = _detect_used_ram_gib()
    selected_index = _coerce_int(selected_gpu_index)
    gpu_devices = _detect_gpu_devices(selected_index)
    selected_gpu = next((device for device in gpu_devices if device.get("selected")), None)
    vram_total = _coerce_float((selected_gpu or {}).get("totalGiB"))
    vram_used = _coerce_float((selected_gpu or {}).get("usedGiB"))
    gpu_name = str((selected_gpu or {}).get("name", "") or "")
    if not gpu_name:
        first_gpu = gpu_devices[0] if gpu_devices else {}
        vram_total = vram_total if vram_total is not None else _coerce_float(first_gpu.get("totalGiB"))
        vram_used = vram_used if vram_used is not None else _coerce_float(first_gpu.get("usedGiB"))
        gpu_name = str(first_gpu.get("name", "") or "")
    fallback_vram_total = vram_total if vram_total is not None else detect_vram_gib()
    return {
        "hostname": socket.gethostname(),
        "platformLabel": platform_label,
        "cpuPercent": _detect_cpu_percent(),
        "ramTotalGiB": ram_total,
        "ramUsedGiB": ram_used,
        "ramFreeGiB": _difference_or_none(ram_total, ram_used),
        "gpuAvailable": vram_total is not None or vram_used is not None or bool(gpu_name),
        "gpuName": gpu_name or "nije dostupan",
        "vramTotalGiB": fallback_vram_total,
        "vramUsedGiB": vram_used,
        "vramFreeGiB": _difference_or_none(fallback_vram_total, vram_used),
        "gpuDevices": gpu_devices,
    }


def _detect_cpu_percent() -> float | None:
    metrics = _load_windows_system_metrics()
    if metrics["cpuPercent"] is not None:
        return metrics["cpuPercent"]
    try:
        if os.name == "nt":
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "[math]::Round((Get-Counter '\\Processor(_Total)\\% Processor Time').CounterSamples[0].CookedValue, 1)",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=8,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if completed.returncode == 0:
                return _coerce_float(completed.stdout.strip())
        return None
    except Exception:  # noqa: BLE001
        return None


def _detect_used_ram_gib() -> float | None:
    metrics = _load_windows_system_metrics()
    if metrics["ramUsedGiB"] is not None:
        return metrics["ramUsedGiB"]
    try:
        if os.name == "nt":
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "[math]::Round(((Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize - (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory) / 1MB, 2)",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=8,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if completed.returncode == 0:
                return _coerce_float(completed.stdout.strip())
        return None
    except Exception:  # noqa: BLE001
        return None


def _load_windows_system_metrics() -> dict[str, float | None]:
    global _WINDOWS_SYSTEM_METRICS_CACHE

    if os.name != "nt":
        return {"cpuPercent": None, "ramUsedGiB": None}

    now = time.monotonic()
    if _WINDOWS_SYSTEM_METRICS_CACHE is not None:
        cached_at, cached_payload = _WINDOWS_SYSTEM_METRICS_CACHE
        if (now - cached_at) <= WINDOWS_SYSTEM_METRICS_CACHE_TTL_SECONDS:
            return cached_payload

    payload = {"cpuPercent": None, "ramUsedGiB": None}
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "$os = Get-CimInstance Win32_OperatingSystem; "
                    "$cpu = (Get-Counter '\\Processor(_Total)\\% Processor Time').CounterSamples[0].CookedValue; "
                    "\"{0}|{1}\" -f [math]::Round($cpu, 1), "
                    "[math]::Round((($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / 1MB), 2)"
                ),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode == 0:
            parts = completed.stdout.strip().split("|", 1)
            payload = {
                "cpuPercent": _coerce_float(parts[0].strip()) if parts else None,
                "ramUsedGiB": _coerce_float(parts[1].strip()) if len(parts) > 1 else None,
            }
    except Exception:  # noqa: BLE001
        payload = {"cpuPercent": None, "ramUsedGiB": None}

    _WINDOWS_SYSTEM_METRICS_CACHE = (time.monotonic(), payload)
    return payload


def _detect_gpu_devices(selected_gpu_index: int | None) -> list[dict[str, Any]]:
    try:
        inventory = _detect_nvidia_gpu_inventory()
    except Exception:  # noqa: BLE001
        inventory = []
    preferred_gpu = _select_preferred_gpu(inventory)
    normalized_selected = selected_gpu_index if selected_gpu_index is not None else int((preferred_gpu or {}).get("index", 0) or 0)
    devices: list[dict[str, Any]] = []
    for device in inventory:
        if not isinstance(device, dict):
            continue
        index = _coerce_int(device.get("index"))
        total_mib = _coerce_float(device.get("totalMemoryMiB"))
        used_mib = _coerce_float(device.get("usedMemoryMiB"))
        total_gib = _mib_to_gib(total_mib)
        used_gib = _mib_to_gib(used_mib)
        devices.append(
            {
                "index": index,
                "name": str(device.get("name", "") or ""),
                "totalGiB": total_gib,
                "usedGiB": used_gib,
                "freeGiB": _difference_or_none(total_gib, used_gib),
                "utilizationPercent": _coerce_float(device.get("utilizationGpuPercent")),
                "selected": index == normalized_selected if index is not None else False,
            }
        )
    return devices


def _build_runtime_resource_snapshot(
    config: ControlCenterConfig,
    runtime_state: dict[str, Any],
) -> dict[str, Any]:
    active_runtime = str(runtime_state.get("active_runtime", "unknown") or "unknown")
    active_model = str(runtime_state.get("active_model", "unknown") or "unknown")
    base_url = str(runtime_state.get("base_url", "") or "")
    port = _coerce_int(runtime_state.get("port"))
    runtime_pid = find_runtime_pid(port or 0) if port else None
    binary_path = Path(str(runtime_state.get("active_binary", "") or ""))
    launch_arguments = (
        _load_runtime_launch_argument_values(
            config,
            runtime_state,
            runtime_name=active_runtime,
            binary_path=binary_path,
        )
        if binary_path.is_file()
        else {}
    )
    runtime_diagnostics = load_runtime_diagnostics(
        runtime_name=active_runtime,
        launch_arguments=launch_arguments,
        log_path=config.install_root / "logs" / "runtime-server.log",
    )
    runtime_diagnostics = _attach_runtime_context_alignment(
        runtime_diagnostics,
        config=config,
        runtime_state=runtime_state,
        runtime_name=active_runtime,
        runtime_pid=runtime_pid,
    )
    selected_gpu_index = _coerce_int(runtime_diagnostics.get("requestedMainGpu"))
    selected_gpu_name = str(runtime_diagnostics.get("deviceLabel", "") or "")
    gpu_devices = _detect_gpu_devices(selected_gpu_index)
    if not selected_gpu_name:
        selected_gpu = next((device for device in gpu_devices if device.get("selected")), None)
        selected_gpu_name = str((selected_gpu or {}).get("name", "") or "")
    selected_gpu = next((device for device in gpu_devices if device.get("selected")), None)
    return {
        "activeRuntime": active_runtime,
        "activeModel": active_model,
        "runtimeLiveStatus": str(runtime_state.get("runtime_live_status", "unknown") or "unknown"),
        "runtimeLiveReason": str(runtime_state.get("runtime_live_reason", "") or ""),
        "baseUrl": base_url,
        "port": port,
        "runtimePid": runtime_pid,
        "runtimeProcessRamMiB": _detect_process_working_set_mib(runtime_pid),
        "executionModeId": str(runtime_diagnostics.get("executionModeId", "unknown") or "unknown"),
        "executionModeLabel": str(runtime_diagnostics.get("executionModeLabel", "") or "Čeka potvrdu"),
        "executionModeSummary": str(runtime_diagnostics.get("executionModeSummary", "") or ""),
        "offloadStatus": str(runtime_diagnostics.get("status", "unknown") or "unknown"),
        "offloadLabel": _build_offload_label(str(runtime_diagnostics.get("status", "unknown") or "unknown")),
        "offloadSummary": str(runtime_diagnostics.get("summary", "") or ""),
        "selectedGpuIndex": selected_gpu_index,
        "selectedGpuName": selected_gpu_name,
        "selectedGpuTotalGiB": _coerce_float((selected_gpu or {}).get("totalGiB")),
        "runtimeDiagnostics": runtime_diagnostics,
    }


def _detect_process_working_set_mib(pid: int | None) -> float | None:
    if not pid:
        return None
    now = time.monotonic()
    with _PROCESS_WORKING_SET_CACHE_LOCK:
        cached_payload = _PROCESS_WORKING_SET_CACHE.get(pid)
        if cached_payload is not None:
            cached_at, cached_value = cached_payload
            if (now - cached_at) <= PROCESS_WORKING_SET_CACHE_TTL_SECONDS:
                return cached_value
    try:
        if os.name == "nt":
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"[math]::Round((Get-Process -Id {pid} -ErrorAction Stop).WorkingSet64 / 1MB, 2)",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=8,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if completed.returncode == 0:
                value = _coerce_float(completed.stdout.strip())
                with _PROCESS_WORKING_SET_CACHE_LOCK:
                    _PROCESS_WORKING_SET_CACHE[pid] = (time.monotonic(), value)
                return value
        return None
    except Exception:  # noqa: BLE001
        return None


def _build_offload_label(status: str) -> str:
    normalized = str(status or "").strip().lower()
    if normalized == "confirmed":
        return "GPU offload potvrđen"
    if normalized == "requested":
        return "GPU offload tražen"
    if normalized == "cpu-only":
        return "CPU-only signal"
    return "Čeka potvrdu"


def _load_recent_log_signals(
    config: ControlCenterConfig | None = None,
) -> list[dict[str, str]]:
    config = config or get_config()
    logs_root = config.install_root / "logs"
    if not logs_root.is_dir():
        return []

    interesting_terms = {
        "error": "error",
        "exception": "error",
        "traceback": "error",
        "failed": "warning",
        "warning": "warning",
        "restart": "info",
        "started": "info",
    }
    signals: list[dict[str, str]] = []
    for log_path in sorted(logs_root.glob("*.log")):
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines[-80:]:
            lower = line.lower()
            level = next((mapped for term, mapped in interesting_terms.items() if term in lower), "")
            if not level:
                continue
            signals.append(
                {
                    "level": level,
                    "source": log_path.name,
                    "message": line.strip()[:240],
                    "timestamp": _iso_from_mtime(log_path),
                }
            )
    return signals[-8:]


def _difference_or_none(total: float | None, used: float | None) -> float | None:
    if total is None or used is None:
        return None
    return round(max(total - used, 0.0), 2)


def _mib_to_gib(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value / 1024, 2)


def _coerce_int(value: object) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _coerce_float(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        return round(float(str(value)), 2)
    except (TypeError, ValueError):
        return None


def _iso_from_mtime(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        return _utc_now()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
