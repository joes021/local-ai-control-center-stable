from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import platform
import socket
import subprocess
from typing import Any

from local_ai_control_center_installer.control_center_backend.config import (
    ControlCenterConfig,
    get_config,
)
from local_ai_control_center_installer.control_center_backend.services.benchmark_service import (
    load_benchmark_summary,
)
from local_ai_control_center_installer.control_center_backend.services.server_service import (
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


def load_observability_payload(
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    config = config or get_config()
    runtime_state = load_runtime_state(config)
    runtime_snapshot = _build_runtime_resource_snapshot(config, runtime_state)
    benchmark_summary = load_benchmark_summary(config)
    telemetry = dict(benchmark_summary.get("telemetry", {}) or {})
    activity = dict(benchmark_summary.get("activity", {}) or {})

    return {
        "generatedAt": _utc_now(),
        "system": _detect_system_snapshot(config, selected_gpu_index=runtime_snapshot.get("selectedGpuIndex")),
        "runtime": runtime_snapshot,
        "telemetry": {
            "input24h": _coerce_int(telemetry.get("input24h")) or 0,
            "output24h": _coerce_int(telemetry.get("output24h")) or 0,
            "total24h": _coerce_int(telemetry.get("total24h")) or 0,
            "cost24hUsd": _coerce_float(telemetry.get("cost24hUsd")) or 0.0,
            "activeRoutes": _coerce_int(telemetry.get("activeRoutes")) or 0,
            "activeRoutesLabel": str(telemetry.get("activeRoutesLabel", "") or "--"),
            "liveNowTokensPerSecond": _coerce_float(telemetry.get("liveNowTokensPerSecond")),
            "flowStateLabel": str(telemetry.get("flowStateLabel", "") or "idle"),
            "flowStateReason": str(telemetry.get("flowStateReason", "") or ""),
            "lastUpdatedAt": str(telemetry.get("lastUpdatedAt", "") or ""),
            "promptSharePercent": _coerce_float(telemetry.get("promptSharePercent")) or 0.0,
            "completionSharePercent": _coerce_float(telemetry.get("completionSharePercent")) or 0.0,
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
    return {
        "hostname": socket.gethostname(),
        "platformLabel": platform_label,
        "cpuPercent": _detect_cpu_percent(),
        "ramTotalGiB": ram_total,
        "ramUsedGiB": ram_used,
        "ramFreeGiB": _difference_or_none(ram_total, ram_used),
        "gpuAvailable": vram_total is not None or vram_used is not None or bool(gpu_name),
        "gpuName": gpu_name or "nije dostupan",
        "vramTotalGiB": vram_total if vram_total is not None else detect_vram_gib(),
        "vramUsedGiB": vram_used,
        "vramFreeGiB": _difference_or_none(vram_total if vram_total is not None else detect_vram_gib(), vram_used),
        "gpuDevices": gpu_devices,
    }


def _detect_cpu_percent() -> float | None:
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
            )
            if completed.returncode == 0:
                return _coerce_float(completed.stdout.strip())
        return None
    except Exception:  # noqa: BLE001
        return None


def _detect_used_ram_gib() -> float | None:
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
            )
            if completed.returncode == 0:
                return _coerce_float(completed.stdout.strip())
        return None
    except Exception:  # noqa: BLE001
        return None


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
            )
            if completed.returncode == 0:
                return _coerce_float(completed.stdout.strip())
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
