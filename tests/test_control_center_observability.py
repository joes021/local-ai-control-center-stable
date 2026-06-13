import importlib
import json
import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.config import get_config
from local_ai_control_center_installer.control_center_backend.main import app


def _write_runtime_endpoint_config(install_root: Path, *, port: int = 39281) -> None:
    config_root = install_root / "config"
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "runtime-endpoint.json").write_text(
        json.dumps({"port": port, "base_url": f"http://127.0.0.1:{port}"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_active_model_config(install_root: Path, *, filename: str = "gemma-4-E4B-it-Q4_K_M.gguf") -> None:
    config_root = install_root / "config"
    config_root.mkdir(parents=True, exist_ok=True)
    model_path = install_root / "models" / "recommended-6gb" / filename
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text("model", encoding="utf-8")
    (config_root / "active-model.json").write_text(
        json.dumps({"model_id": "recommended-6gb", "model_path": str(model_path)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_observability_route_returns_runtime_system_and_log_summary(tmp_path: Path, monkeypatch):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_runtime_endpoint_config(install_root)
    _write_active_model_config(install_root)

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.observability_service._detect_system_snapshot",
        lambda config=None, selected_gpu_index=None: {
            "hostname": "gpu-box",
            "platformLabel": "Windows",
            "cpuPercent": 19.4,
            "ramTotalGiB": 32.0,
            "ramUsedGiB": 14.2,
            "ramFreeGiB": 17.8,
            "gpuAvailable": True,
            "gpuName": "RTX 3060",
            "vramTotalGiB": 12.0,
            "vramUsedGiB": 7.3,
            "vramFreeGiB": 4.7,
            "gpuDevices": [
                {
                    "index": 0,
                    "name": "RTX 3060",
                    "totalGiB": 12.0,
                    "usedGiB": 7.3,
                    "freeGiB": 4.7,
                    "selected": True,
                }
            ],
        },
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.observability_service.load_runtime_state",
        lambda config=None: {
            "active_model": "Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf",
            "active_model_id": "qwen",
            "active_runtime": "turboquant",
            "runtime_live_status": "started",
            "runtime_live_reason": "Runtime healthy.",
            "base_url": "http://127.0.0.1:39281",
            "port": 39281,
        },
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.observability_service.load_benchmark_summary",
        lambda config=None: {
            "requestCount": 9,
            "lastMeasuredAt": "2026-05-27T12:00:00+00:00",
            "current": {"totalMs": 1280.0},
            "telemetry": {
                "input24h": 50789,
                "output24h": 25552,
                "total24h": 76341,
                "cost24hUsd": 0.0076,
                "activeRoutes": 1,
                "activeRoutesLabel": "Llama.cpp / Qwen 3.6 35B A3B / benchmark",
                "liveNowTokensPerSecond": 21.8,
                "flowStateLabel": "active generation",
                "flowStateReason": "live route signal",
                "lastUpdatedAt": "2026-05-27T02:35:23+00:00",
                "promptSharePercent": 66.5,
                "completionSharePercent": 33.5,
                "launchQueueSignal": {"label": "quiet", "summary": "No backlog"},
            },
            "activity": {
                "averageTotalMs": 1402.0,
                "stability": {
                    "label": "stable",
                    "score": 91,
                    "reason": "steady",
                },
            },
        },
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.observability_service._load_recent_log_signals",
        lambda config=None: [
            {"level": "error", "source": "runtime-server.log", "message": "CUDA oom", "timestamp": "2026-05-27T11:00:00+00:00"}
        ],
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.observability_service._build_runtime_resource_snapshot",
        lambda config, runtime_state: {
            "activeRuntime": "turboquant",
            "activeModel": "Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf",
            "runtimeLiveStatus": "started",
            "runtimeLiveReason": "Runtime healthy.",
            "baseUrl": "http://127.0.0.1:39281",
            "port": 39281,
            "executionModeId": "gpu-vram",
            "executionModeLabel": "GPU VRAM dominantno",
            "executionModeSummary": "Svi slojevi su potvrđeni na GPU-u.",
            "offloadStatus": "confirmed",
            "offloadLabel": "GPU offload potvrđen",
            "offloadSummary": "Runtime log potvrđuje CUDA offload.",
            "selectedGpuIndex": 0,
            "selectedGpuName": "RTX 3060",
            "selectedGpuTotalGiB": 12.0,
            "runtimeProcessRamMiB": 6285.0,
        },
    )

    client = TestClient(app)
    response = client.get("/api/observability")

    assert response.status_code == 200
    payload = response.json()
    assert payload["system"]["hostname"] == "gpu-box"
    assert payload["system"]["gpuName"] == "RTX 3060"
    assert payload["system"]["gpuDevices"][0]["selected"] is True
    assert payload["runtime"]["activeRuntime"] == "turboquant"
    assert payload["runtime"]["runtimeLiveStatus"] == "started"
    assert payload["runtime"]["executionModeLabel"] == "GPU VRAM dominantno"
    assert payload["runtime"]["offloadStatus"] == "confirmed"
    assert payload["telemetry"]["input24h"] == 50789
    assert payload["telemetry"]["liveNowTokensPerSecond"] == 21.8
    assert payload["activity"]["requestCount"] == 9
    assert payload["activity"]["averageTotalMs"] == 1402.0
    assert payload["logSignals"][0]["message"] == "CUDA oom"


def test_observability_route_keeps_runtime_context_alignment_signal(tmp_path: Path, monkeypatch):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_runtime_endpoint_config(install_root)
    _write_active_model_config(install_root)

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.observability_service._detect_system_snapshot",
        lambda config=None, selected_gpu_index=None: {
            "hostname": "gpu-box",
            "platformLabel": "Windows",
            "cpuPercent": 19.4,
            "ramTotalGiB": 32.0,
            "ramUsedGiB": 14.2,
            "ramFreeGiB": 17.8,
            "gpuAvailable": True,
            "gpuName": "RTX 3060",
            "vramTotalGiB": 12.0,
            "vramUsedGiB": 7.3,
            "vramFreeGiB": 4.7,
            "gpuDevices": [],
        },
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.observability_service.load_runtime_state",
        lambda config=None: {
            "active_model": "Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf",
            "active_model_id": "qwen",
            "active_runtime": "turboquant",
            "runtime_live_status": "started",
            "runtime_live_reason": "Runtime healthy.",
            "base_url": "http://127.0.0.1:39281",
            "port": 39281,
        },
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.observability_service.load_benchmark_summary",
        lambda config=None: {
            "requestCount": 9,
            "lastMeasuredAt": "2026-05-31T12:00:00+00:00",
            "telemetry": {},
            "activity": {
                "averageTotalMs": 1402.0,
                "stability": {
                    "label": "stable",
                    "score": 91,
                    "reason": "steady",
                },
            },
        },
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.observability_service._load_recent_log_signals",
        lambda config=None: [],
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.observability_service._build_runtime_resource_snapshot",
        lambda config, runtime_state: {
            "activeRuntime": "turboquant",
            "activeModel": "Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf",
            "runtimeLiveStatus": "started",
            "runtimeLiveReason": "Runtime healthy.",
            "baseUrl": "http://127.0.0.1:39281",
            "port": 39281,
            "executionModeId": "gpu-vram",
            "executionModeLabel": "GPU VRAM dominantno",
            "executionModeSummary": "Svi slojevi su potvrđeni na GPU-u.",
            "offloadStatus": "confirmed",
            "offloadLabel": "GPU offload potvrđen",
            "offloadSummary": "Runtime log potvrđuje CUDA offload.",
            "selectedGpuIndex": 0,
            "selectedGpuName": "RTX 3060",
            "selectedGpuTotalGiB": 12.0,
            "runtimeProcessRamMiB": 6285.0,
            "runtimeDiagnostics": {
                "status": "confirmed",
                "backend": "CUDA",
                "deviceLabel": "RTX 3060",
                "requestedGpuLayers": 41,
                "requestedFlashAttention": "auto",
                "requestedMainGpu": 0,
                "requestedSplitMode": "none",
                "projectedDeviceMemoryMiB": 17309,
                "projectedHostMemoryMiB": 16154,
                "confirmedGpuLayers": 41,
                "confirmedTotalLayers": 41,
                "cpuMappedModelBufferMiB": 272.81,
                "modelBufferMiB": 16181.49,
                "kvBufferMiB": 380.0,
                "computeBufferMiB": 46.02,
                "executionModeId": "gpu-vram",
                "executionModeLabel": "GPU VRAM dominantno",
                "executionModeSummary": "Svi slojevi su potvrđeni na GPU-u.",
                "requestedSummary": "Launch komanda traži --n-gpu-layers 41",
                "confirmedSummary": "Runtime log potvrđuje CUDA.",
                "summary": "GPU offload je potvrđen kroz runtime log.",
                "notes": [],
                "configuredContext": 16384,
                "effectiveProcessContext": 19456,
                "contextMismatch": True,
                "contextAlignmentLabel": "Potreban restart runtime-a",
                "contextAlignmentSummary": "Config traži 16384, a živi proces i dalje radi sa 19456.",
            },
        },
    )

    client = TestClient(app)
    response = client.get("/api/observability")

    assert response.status_code == 200
    payload = response.json()
    assert payload["runtime"]["runtimeDiagnostics"]["configuredContext"] == 16384
    assert payload["runtime"]["runtimeDiagnostics"]["effectiveProcessContext"] == 19456
    assert payload["runtime"]["runtimeDiagnostics"]["contextMismatch"] is True


def test_observability_route_reads_current_benchmark_telemetry_field_names(tmp_path: Path, monkeypatch):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_runtime_endpoint_config(install_root)
    _write_active_model_config(install_root)

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.observability_service._detect_system_snapshot",
        lambda config=None, selected_gpu_index=None: {
            "hostname": "gpu-box",
            "platformLabel": "Windows",
            "cpuPercent": 19.4,
            "ramTotalGiB": 32.0,
            "ramUsedGiB": 14.2,
            "ramFreeGiB": 17.8,
            "gpuAvailable": True,
            "gpuName": "RTX 3060",
            "vramTotalGiB": 12.0,
            "vramUsedGiB": 7.3,
            "vramFreeGiB": 4.7,
            "gpuDevices": [],
        },
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.observability_service.load_runtime_state",
        lambda config=None: {
            "active_model": "Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf",
            "active_model_id": "qwen",
            "active_runtime": "turboquant",
            "runtime_live_status": "started",
            "runtime_live_reason": "Runtime healthy.",
            "base_url": "http://127.0.0.1:39281",
            "port": 39281,
        },
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.observability_service.load_benchmark_summary",
        lambda config=None: {
            "requestCount": 9,
            "lastMeasuredAt": "2026-05-31T12:00:00+00:00",
            "telemetry": {
                "input24hTokens": 50789,
                "output24hTokens": 25552,
                "total24hTokens": 76341,
                "estimatedCost24hUsd": 0.0076,
                "activeRoutes": 1,
                "activeRoutesLabel": "TurboQuant / Qwen / runtime-live",
                "liveNowTokensPerSecond": 21.8,
                "flowStateLabel": "active generation",
                "flowStateReason": "live route signal",
                "lastUpdate": "2026-05-31T12:35:23+00:00",
                "inputSharePercent": 66.5,
                "outputSharePercent": 33.5,
                "launchQueueSignal": {"label": "quiet", "summary": "No backlog"},
            },
            "activity": {
                "averageTotalMs": 1402.0,
                "stability": {
                    "label": "stable",
                    "score": 91,
                    "reason": "steady",
                },
            },
        },
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.observability_service._load_recent_log_signals",
        lambda config=None: [],
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.observability_service._build_runtime_resource_snapshot",
        lambda config, runtime_state: {
            "activeRuntime": "turboquant",
            "activeModel": "Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf",
            "runtimeLiveStatus": "started",
            "runtimeLiveReason": "Runtime healthy.",
            "baseUrl": "http://127.0.0.1:39281",
            "port": 39281,
            "executionModeId": "gpu-vram",
            "executionModeLabel": "GPU VRAM dominantno",
            "executionModeSummary": "Svi slojevi su potvrđeni na GPU-u.",
            "offloadStatus": "confirmed",
            "offloadLabel": "GPU offload potvrđen",
            "offloadSummary": "Runtime log potvrđuje CUDA offload.",
            "selectedGpuIndex": 0,
            "selectedGpuName": "RTX 3060",
            "selectedGpuTotalGiB": 12.0,
            "runtimeProcessRamMiB": 6285.0,
        },
    )

    client = TestClient(app)
    response = client.get("/api/observability")

    assert response.status_code == 200
    payload = response.json()
    assert payload["telemetry"]["input24h"] == 50789
    assert payload["telemetry"]["output24h"] == 25552
    assert payload["telemetry"]["total24h"] == 76341
    assert payload["telemetry"]["cost24hUsd"] == 0.01
    assert payload["telemetry"]["lastUpdatedAt"] == "2026-05-31T12:35:23+00:00"
    assert payload["telemetry"]["promptSharePercent"] == 66.5
    assert payload["telemetry"]["completionSharePercent"] == 33.5


def test_load_observability_payload_reuses_recent_snapshot(monkeypatch, tmp_path: Path):
    module = importlib.import_module(
        "local_ai_control_center_installer.control_center_backend.services.observability_service"
    )
    module = importlib.reload(module)

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()

    calls = {
        "runtime": 0,
        "benchmark": 0,
        "system": 0,
        "logs": 0,
        "snapshot": 0,
    }

    def fake_runtime_state(config=None):
        calls["runtime"] += 1
        return {
            "active_model": "Demo.gguf",
            "active_runtime": "llama.cpp",
            "runtime_live_status": "started",
            "runtime_live_reason": "ok",
            "base_url": "http://127.0.0.1:39281",
            "port": 39281,
        }

    def fake_runtime_snapshot(config, runtime_state):
        calls["snapshot"] += 1
        return {
            "activeRuntime": "llama.cpp",
            "activeModel": "Demo.gguf",
            "runtimeLiveStatus": "started",
            "runtimeLiveReason": "ok",
            "baseUrl": "http://127.0.0.1:39281",
            "port": 39281,
            "selectedGpuIndex": 0,
            "runtimeDiagnostics": {},
        }

    def fake_benchmark(config=None):
        calls["benchmark"] += 1
        return {
            "requestCount": 1,
            "lastMeasuredAt": "2026-06-09T12:00:00+00:00",
            "telemetry": {},
            "activity": {"stability": {}},
        }

    def fake_system(config=None, selected_gpu_index=None):
        calls["system"] += 1
        return {
            "hostname": "gpu-box",
            "platformLabel": "Windows",
            "cpuPercent": 10.0,
            "ramTotalGiB": 32.0,
            "ramUsedGiB": 12.0,
            "ramFreeGiB": 20.0,
            "gpuAvailable": True,
            "gpuName": "RTX 3060",
            "vramTotalGiB": 12.0,
            "vramUsedGiB": 4.0,
            "vramFreeGiB": 8.0,
            "gpuDevices": [],
        }

    def fake_logs(config=None):
        calls["logs"] += 1
        return []

    monkeypatch.setattr(module, "load_runtime_state", fake_runtime_state)
    monkeypatch.setattr(module, "_build_runtime_resource_snapshot", fake_runtime_snapshot)
    monkeypatch.setattr(module, "load_benchmark_summary", fake_benchmark)
    monkeypatch.setattr(module, "_detect_system_snapshot", fake_system)
    monkeypatch.setattr(module, "_load_recent_log_signals", fake_logs)

    first = module.load_observability_payload(config)
    second = module.load_observability_payload(config)

    assert first["runtime"]["activeModel"] == "Demo.gguf"
    assert second["runtime"]["activeModel"] == "Demo.gguf"
    assert calls == {
        "runtime": 1,
        "benchmark": 1,
        "system": 1,
        "logs": 1,
        "snapshot": 1,
    }


def test_load_observability_payload_deduplicates_parallel_cold_requests(monkeypatch, tmp_path: Path):
    module = importlib.import_module(
        "local_ai_control_center_installer.control_center_backend.services.observability_service"
    )
    module = importlib.reload(module)

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()

    calls = {
        "runtime": 0,
        "benchmark": 0,
        "system": 0,
        "logs": 0,
        "snapshot": 0,
    }
    first_call_entered = threading.Event()
    release_first_call = threading.Event()
    results: list[dict[str, object]] = []
    errors: list[BaseException] = []

    def fake_runtime_state(config=None):
        calls["runtime"] += 1
        return {
            "active_model": "Demo.gguf",
            "active_runtime": "llama.cpp",
            "runtime_live_status": "started",
            "runtime_live_reason": "ok",
            "base_url": "http://127.0.0.1:39281",
            "port": 39281,
        }

    def fake_runtime_snapshot(config, runtime_state):
        calls["snapshot"] += 1
        if calls["snapshot"] == 1:
            first_call_entered.set()
            assert release_first_call.wait(timeout=5)
        return {
            "activeRuntime": "llama.cpp",
            "activeModel": "Demo.gguf",
            "runtimeLiveStatus": "started",
            "runtimeLiveReason": "ok",
            "baseUrl": "http://127.0.0.1:39281",
            "port": 39281,
            "selectedGpuIndex": 0,
            "runtimeDiagnostics": {},
        }

    def fake_benchmark(config=None):
        calls["benchmark"] += 1
        return {
            "requestCount": 1,
            "lastMeasuredAt": "2026-06-09T12:00:00+00:00",
            "telemetry": {},
            "activity": {"stability": {}},
        }

    def fake_system(config=None, selected_gpu_index=None):
        calls["system"] += 1
        return {
            "hostname": "gpu-box",
            "platformLabel": "Windows",
            "cpuPercent": 10.0,
            "ramTotalGiB": 32.0,
            "ramUsedGiB": 12.0,
            "ramFreeGiB": 20.0,
            "gpuAvailable": True,
            "gpuName": "RTX 3060",
            "vramTotalGiB": 12.0,
            "vramUsedGiB": 4.0,
            "vramFreeGiB": 8.0,
            "gpuDevices": [],
        }

    def fake_logs(config=None):
        calls["logs"] += 1
        return []

    monkeypatch.setattr(module, "load_runtime_state", fake_runtime_state)
    monkeypatch.setattr(module, "_build_runtime_resource_snapshot", fake_runtime_snapshot)
    monkeypatch.setattr(module, "load_benchmark_summary", fake_benchmark)
    monkeypatch.setattr(module, "_detect_system_snapshot", fake_system)
    monkeypatch.setattr(module, "_load_recent_log_signals", fake_logs)

    def worker() -> None:
        try:
            results.append(module.load_observability_payload(config))
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    first_thread = threading.Thread(target=worker, daemon=True)
    second_thread = threading.Thread(target=worker, daemon=True)
    first_thread.start()
    assert first_call_entered.wait(timeout=5)
    second_thread.start()
    time.sleep(0.1)
    release_first_call.set()
    first_thread.join(timeout=5)
    second_thread.join(timeout=5)

    assert errors == []
    assert len(results) == 2
    assert calls == {
        "runtime": 1,
        "benchmark": 1,
        "system": 1,
        "logs": 1,
        "snapshot": 1,
    }


def test_load_runtime_resource_snapshot_reuses_recent_probe_data(monkeypatch, tmp_path: Path):
    module = importlib.import_module(
        "local_ai_control_center_installer.control_center_backend.services.observability_service"
    )
    module = importlib.reload(module)

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()
    runtime_state = {
        "active_model": "Demo.gguf",
        "active_runtime": "llama.cpp",
        "runtime_live_status": "started",
        "runtime_live_reason": "ok",
        "base_url": "http://127.0.0.1:39281",
        "port": 39281,
    }
    calls = {"snapshot": 0}

    monkeypatch.setattr(
        module,
        "_build_runtime_resource_snapshot",
        lambda config, runtime_state: (
            calls.__setitem__("snapshot", calls["snapshot"] + 1) or {
                "activeRuntime": "llama.cpp",
                "activeModel": "Demo.gguf",
            }
        ),
    )

    first = module.load_runtime_resource_snapshot(config, runtime_state)
    second = module.load_runtime_resource_snapshot(config, runtime_state)

    assert first["activeRuntime"] == "llama.cpp"
    assert second["activeModel"] == "Demo.gguf"
    assert calls == {"snapshot": 1}


def test_load_runtime_resource_snapshot_deduplicates_parallel_cold_requests(monkeypatch, tmp_path: Path):
    module = importlib.import_module(
        "local_ai_control_center_installer.control_center_backend.services.observability_service"
    )
    module = importlib.reload(module)

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()
    runtime_state = {
        "active_model": "Demo.gguf",
        "active_runtime": "llama.cpp",
        "runtime_live_status": "started",
        "runtime_live_reason": "ok",
        "base_url": "http://127.0.0.1:39281",
        "port": 39281,
    }
    calls = {"snapshot": 0}
    first_call_entered = threading.Event()
    release_first_call = threading.Event()
    results: list[dict[str, object]] = []
    errors: list[BaseException] = []

    def fake_runtime_snapshot(config, runtime_state):
        calls["snapshot"] += 1
        if calls["snapshot"] == 1:
            first_call_entered.set()
            assert release_first_call.wait(timeout=5)
        return {"activeRuntime": "llama.cpp", "activeModel": "Demo.gguf"}

    monkeypatch.setattr(module, "_build_runtime_resource_snapshot", fake_runtime_snapshot)

    def worker() -> None:
        try:
            results.append(module.load_runtime_resource_snapshot(config, runtime_state))
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    first_thread = threading.Thread(target=worker, daemon=True)
    second_thread = threading.Thread(target=worker, daemon=True)
    first_thread.start()
    assert first_call_entered.wait(timeout=5)
    second_thread.start()
    time.sleep(0.1)
    release_first_call.set()
    first_thread.join(timeout=5)
    second_thread.join(timeout=5)

    assert errors == []
    assert len(results) == 2
    assert all(result["activeRuntime"] == "llama.cpp" for result in results)
    assert calls == {"snapshot": 1}


def test_load_system_snapshot_reuses_recent_probe_data(monkeypatch, tmp_path: Path):
    module = importlib.import_module(
        "local_ai_control_center_installer.control_center_backend.services.observability_service"
    )
    module = importlib.reload(module)

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()
    calls = {"system": 0}

    monkeypatch.setattr(
        module,
        "_detect_system_snapshot",
        lambda config=None, selected_gpu_index=None: (
            calls.__setitem__("system", calls["system"] + 1) or {
                "hostname": "gpu-box",
                "gpuName": "RTX 3060",
                "selectedGpuIndex": selected_gpu_index,
            }
        ),
    )

    first = module.load_system_snapshot(config, selected_gpu_index=0)
    second = module.load_system_snapshot(config, selected_gpu_index=0)

    assert first["gpuName"] == "RTX 3060"
    assert second["gpuName"] == "RTX 3060"
    assert calls == {"system": 1}


def test_load_system_snapshot_deduplicates_parallel_cold_requests(monkeypatch, tmp_path: Path):
    module = importlib.import_module(
        "local_ai_control_center_installer.control_center_backend.services.observability_service"
    )
    module = importlib.reload(module)

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()
    calls = {"system": 0}
    first_call_entered = threading.Event()
    release_first_call = threading.Event()
    results: list[dict[str, object]] = []
    errors: list[BaseException] = []

    def fake_system_snapshot(config=None, selected_gpu_index=None):
        calls["system"] += 1
        if calls["system"] == 1:
            first_call_entered.set()
            assert release_first_call.wait(timeout=5)
        return {"hostname": "gpu-box", "gpuName": "RTX 3060"}

    monkeypatch.setattr(module, "_detect_system_snapshot", fake_system_snapshot)

    def worker() -> None:
        try:
            results.append(module.load_system_snapshot(config, selected_gpu_index=0))
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    first_thread = threading.Thread(target=worker, daemon=True)
    second_thread = threading.Thread(target=worker, daemon=True)
    first_thread.start()
    assert first_call_entered.wait(timeout=5)
    second_thread.start()
    time.sleep(0.1)
    release_first_call.set()
    first_thread.join(timeout=5)
    second_thread.join(timeout=5)

    assert errors == []
    assert len(results) == 2
    assert all(result["gpuName"] == "RTX 3060" for result in results)
    assert calls == {"system": 1}


def test_detect_process_working_set_mib_reuses_recent_windows_probe(monkeypatch):
    module = importlib.import_module(
        "local_ai_control_center_installer.control_center_backend.services.observability_service"
    )
    module = importlib.reload(module)

    calls = {"run": 0}

    class FakeCompletedProcess:
        returncode = 0
        stdout = "6285.0"
        stderr = ""

    def fake_run(*args, **kwargs):
        calls["run"] += 1
        return FakeCompletedProcess()

    monkeypatch.setattr(module.os, "name", "nt", raising=False)
    monkeypatch.setattr(module.subprocess, "run", fake_run)

    first = module._detect_process_working_set_mib(5150)
    second = module._detect_process_working_set_mib(5150)

    assert first == 6285.0
    assert second == first
    assert calls == {"run": 1}


def test_load_windows_system_metrics_reuses_recent_probe(monkeypatch):
    module = importlib.import_module(
        "local_ai_control_center_installer.control_center_backend.services.observability_service"
    )
    module = importlib.reload(module)

    calls: list[dict[str, object]] = []

    class FakeCompletedProcess:
        returncode = 0
        stdout = "27.4|18.25"
        stderr = ""

    def fake_run(*args, **kwargs):
        calls.append(kwargs)
        return FakeCompletedProcess()

    monkeypatch.setattr(module.os, "name", "nt", raising=False)
    monkeypatch.setattr(module.subprocess, "run", fake_run)

    first = module._load_windows_system_metrics()
    second = module._load_windows_system_metrics()

    assert first == {"cpuPercent": 27.4, "ramUsedGiB": 18.25}
    assert second == first
    assert len(calls) == 1
    assert calls[0]["creationflags"] == getattr(module.subprocess, "CREATE_NO_WINDOW", 0)
