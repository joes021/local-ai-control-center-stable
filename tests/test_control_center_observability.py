import json
from pathlib import Path

from fastapi.testclient import TestClient

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
