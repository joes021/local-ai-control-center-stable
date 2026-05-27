import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from local_ai_control_center_installer.control_center_backend.config import get_config


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


def _write_settings_config(
    install_root: Path,
    *,
    profile: str = "video",
    context: int = 131072,
    output_tokens: int = 16384,
    thinking_mode: str = "high",
) -> None:
    control_center_root = install_root / "config" / "control-center"
    control_center_root.mkdir(parents=True, exist_ok=True)
    (control_center_root / "settings.json").write_text(
        json.dumps(
            {
                "profile": profile,
                "context": context,
                "outputTokens": output_tokens,
                "thinkingMode": thinking_mode,
                "buildSteps": 160,
                "planSteps": 120,
                "generalSteps": 130,
                "exploreSteps": 90,
                "accessMode": "local-only",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_control_center_config_exposes_benchmark_state_paths(tmp_path: Path, monkeypatch):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    config = get_config()

    assert config.benchmark_history_path == install_root / "config" / "control-center" / "benchmark-history.json"
    assert config.benchmark_live_history_path == install_root / "config" / "control-center" / "benchmark-live-history.json"
    assert config.benchmark_run_state_path == install_root / "config" / "control-center" / "benchmark-run-state.json"
    assert config.benchmark_batteries_path == install_root / "config" / "control-center" / "benchmark-batteries.json"
    assert config.benchmark_saved_runs_path == install_root / "config" / "control-center" / "benchmark-saved-runs.json"


def test_load_benchmark_summary_reads_installer_managed_history_and_defaults(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import benchmark_service
    from local_ai_control_center_installer.control_center_backend.services.benchmark_service import (
        load_benchmark_summary,
    )

    install_root = tmp_path / "install-root"
    now = datetime.now(timezone.utc)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_runtime_endpoint_config(install_root)
    _write_active_model_config(install_root)
    _write_settings_config(install_root)

    config = get_config()
    config.control_center_config_root.mkdir(parents=True, exist_ok=True)
    config.benchmark_history_path.write_text(
        json.dumps(
            [
                {
                    "measuredAt": (now - timedelta(seconds=45)).isoformat(),
                    "label": "benchmark-short",
                    "promptTokensPerSecond": 20.0,
                    "completionTokensPerSecond": 30.0,
                    "totalTokensPerSecond": 25.0,
                    "totalMs": 1400.0,
                },
                {
                    "measuredAt": (now - timedelta(seconds=15)).isoformat(),
                    "label": "benchmark-medium",
                    "promptTokensPerSecond": 24.0,
                    "completionTokensPerSecond": 36.0,
                    "totalTokensPerSecond": 30.0,
                    "totalMs": 1200.0,
                },
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    config.benchmark_saved_runs_path.write_text(
        json.dumps(
            [
                {
                    "runId": "run-1",
                    "mode": "selected",
                    "batteryName": "Default battery",
                    "scenarioName": "Short",
                    "modelId": "recommended-6gb",
                    "runtime": "llama.cpp",
                    "status": "done",
                    "startedAt": "2026-05-24T10:00:00+00:00",
                    "finishedAt": "2026-05-24T10:01:00+00:00",
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (install_root / "logs").mkdir(parents=True, exist_ok=True)
    (install_root / "logs" / "runtime-server.log").write_text("line-1\nline-2\n", encoding="utf-8")
    monkeypatch.setattr(
        benchmark_service,
        "load_runtime_state",
        lambda config=None: {
            "active_model_id": "recommended-6gb",
            "active_model": "gemma-4-E4B-it-Q4_K_M.gguf",
            "active_runtime": "llama.cpp",
            "runtime_live_status": "stopped",
            "runtime_live_reason": "Runtime trenutno nije pokrenut.",
        },
    )

    payload = load_benchmark_summary()

    assert payload["historyCount"] == 2
    assert payload["requestCount"] == 2
    assert payload["current"]["label"] == "benchmark-medium"
    assert payload["liveCurrent"] is None
    assert payload["averages"]["totalTokensPerSecond"] == 27.5
    assert payload["activity"]["throughputTrend"]["direction"] == "up"
    assert payload["batteries"][0]["id"] == "default"
    assert payload["selectedBattery"]["id"] == "default"
    assert payload["savedRuns"][0]["runId"] == "run-1"
    assert payload["liveLog"]["lines"][-1] == "line-2"
    assert payload["activeRun"]["status"] == "idle"
    assert payload["environment"] == {
        "modelId": "recommended-6gb",
        "modelLabel": "gemma-4-E4B-it-Q4_K_M.gguf",
        "runtime": "llama.cpp",
        "runtimeLabel": "llama.cpp",
        "profile": "video",
        "context": 131072,
        "outputTokens": 16384,
        "thinkingMode": "high",
        "runtimeLiveStatus": "stopped",
        "runtimeLiveReason": "Runtime trenutno nije pokrenut.",
    }
    assert payload["current"]["environment"]["modelLabel"] == "gemma-4-E4B-it-Q4_K_M.gguf"
    assert payload["liveState"] == {
        "status": "recent-benchmark",
        "hasLiveSignal": False,
        "reason": "Runtime trenutno nema aktivan live throughput signal. Prikazujem poslednji benchmark throughput kao referencu dok nema novog live saobraćaja.",
    }
    assert payload["savedRuns"][0]["modelLabel"] == "gemma-4-E4B-it-Q4_K_M.gguf"
    assert payload["savedRuns"][0]["runtimeLabel"] == "llama.cpp"
    assert payload["savedRuns"][0]["context"] == 131072
    assert payload["savedRuns"][0]["outputTokens"] == 16384
    assert payload["savedRuns"][0]["profile"] == "video"
    assert payload["savedRuns"][0]["thinkingMode"] == "high"


def test_load_benchmark_summary_merges_live_slots_signal_into_visible_history(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import benchmark_service

    install_root = tmp_path / "install-root"
    now = datetime.now(timezone.utc)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_runtime_endpoint_config(install_root)
    _write_active_model_config(install_root)
    _write_settings_config(install_root, profile="balanced", context=262144, output_tokens=8192, thinking_mode="mid")

    config = get_config()
    config.control_center_config_root.mkdir(parents=True, exist_ok=True)
    config.benchmark_history_path.write_text(
        json.dumps(
            [
                {
                    "measuredAt": (now - timedelta(seconds=30)).isoformat(),
                    "label": "benchmark-short",
                    "promptTokensPerSecond": 20.0,
                    "completionTokensPerSecond": 30.0,
                    "totalTokensPerSecond": 25.0,
                    "totalMs": 1400.0,
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    live_sample = {
        "measuredAt": (now - timedelta(seconds=5)).isoformat(),
        "label": "opencode-live",
        "promptTokensPerSecond": None,
        "completionTokensPerSecond": 12.0,
        "totalTokensPerSecond": 12.0,
        "totalMs": 5000.0,
        "signature": "opencode-live:test-sample",
    }

    monkeypatch.setattr(benchmark_service, "_load_live_slot_metric", lambda config=None: live_sample)

    payload = benchmark_service.load_benchmark_summary()

    assert payload["historyCount"] == 1
    assert payload["requestCount"] == 1
    assert payload["current"]["label"] == "opencode-live"
    assert payload["liveCurrent"]["label"] == "opencode-live"
    assert payload["history"][-1]["label"] == "opencode-live"
    assert payload["liveHistory"][-1]["label"] == "opencode-live"
    assert payload["activity"]["sources"]["opencode"] == 1
    assert payload["liveState"] == {
        "status": "active",
        "hasLiveSignal": True,
        "reason": "Live throughput signal dolazi iz aktivnog runtime /slots uzorka.",
    }
    assert payload["liveCurrent"]["environment"]["runtimeLabel"] == "llama.cpp"
    assert payload["liveCurrent"]["environment"]["profile"] == "balanced"


def test_load_benchmark_summary_builds_24h_telemetry_snapshot(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import benchmark_service

    install_root = tmp_path / "install-root"
    now = datetime.now(timezone.utc)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_runtime_endpoint_config(install_root)
    _write_active_model_config(install_root, filename="Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf")
    _write_settings_config(install_root, profile="balanced", context=262144, output_tokens=8192, thinking_mode="mid")

    config = get_config()
    config.control_center_config_root.mkdir(parents=True, exist_ok=True)
    config.benchmark_history_path.write_text(
        json.dumps(
            [
                {
                    "measuredAt": (now - timedelta(hours=2)).isoformat(),
                    "label": "benchmark-short",
                    "promptTokens": 50789,
                    "completionTokens": 25552,
                    "totalTokens": 76341,
                    "promptTokensPerSecond": 19.4,
                    "completionTokensPerSecond": 21.8,
                    "totalTokensPerSecond": 21.8,
                    "totalMs": 3500.0,
                },
                {
                    "measuredAt": (now - timedelta(hours=30)).isoformat(),
                    "label": "stale-run",
                    "promptTokens": 500,
                    "completionTokens": 500,
                    "totalTokens": 1000,
                    "promptTokensPerSecond": 5.0,
                    "completionTokensPerSecond": 5.0,
                    "totalTokensPerSecond": 5.0,
                    "totalMs": 2000.0,
                },
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        benchmark_service,
        "load_runtime_state",
        lambda config=None: {
            "active_model_id": "unsloth-unsloth-qwen3-6-35b-a3b-gguf-qwen3-6-35b-a3b-ud-iq2-xxs",
            "active_model": "Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf",
            "active_runtime": "llama.cpp",
            "runtime_live_status": "started",
            "runtime_live_reason": "Runtime je spreman.",
        },
    )
    monkeypatch.setattr(
        benchmark_service,
        "_load_live_slot_metric",
        lambda config=None: {
            "measuredAt": (now - timedelta(seconds=5)).isoformat(),
            "label": "benchmark",
            "promptTokens": 0,
            "completionTokens": 109,
            "totalTokens": 109,
            "promptTokensPerSecond": None,
            "completionTokensPerSecond": 21.8,
            "totalTokensPerSecond": 21.8,
            "totalMs": 5000.0,
            "activeRoutes": 1,
            "signature": "opencode-live:token-pulse",
        },
    )
    monkeypatch.setattr(
        benchmark_service,
        "_load_run_state",
        lambda config=None: {
            "runId": "",
            "status": "idle",
            "mode": "selected",
            "batteryId": "default",
            "batteryName": "Default battery",
            "scenarioId": "",
            "scenarioName": "",
            "currentScenarioId": "",
            "currentScenarioName": "",
            "currentIndex": 0,
            "totalScenarios": 0,
            "percent": 0,
            "startedAt": "",
            "finishedAt": "",
            "message": "Benchmark nije pokrenut.",
            "scenarioStatuses": [],
        },
    )

    payload = benchmark_service.load_benchmark_summary()

    telemetry = payload["telemetry"]

    assert telemetry["input24hTokens"] == 50789
    assert telemetry["output24hTokens"] == 25552
    assert telemetry["total24hTokens"] == 76341
    assert telemetry["estimatedCost24hUsd"] == 0.0076
    assert telemetry["activeRoutes"] == 1
    assert telemetry["activeRoutesLabel"] == "llama.cpp / Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf / benchmark"
    assert telemetry["liveNowTokensPerSecond"] == 21.8
    assert telemetry["flowState"] == "active-generation"
    assert telemetry["flowStateLabel"] == "active generation"
    assert telemetry["inputSharePercent"] == 66.5
    assert telemetry["outputSharePercent"] == 33.5


def test_load_benchmark_summary_falls_back_to_recent_benchmark_throughput_when_live_signal_is_idle(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import benchmark_service

    install_root = tmp_path / "install-root"
    now = datetime.now(timezone.utc)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_runtime_endpoint_config(install_root)
    _write_active_model_config(install_root, filename="Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf")
    _write_settings_config(install_root, profile="balanced", context=262144, output_tokens=8192, thinking_mode="mid")

    config = get_config()
    config.control_center_config_root.mkdir(parents=True, exist_ok=True)
    config.benchmark_history_path.write_text(
        json.dumps(
            [
                {
                    "measuredAt": (now - timedelta(minutes=4)).isoformat(),
                    "label": "benchmark-full-battery",
                    "promptTokens": 24000,
                    "completionTokens": 12000,
                    "totalTokens": 36000,
                    "promptTokensPerSecond": 16.2,
                    "completionTokensPerSecond": 19.4,
                    "totalTokensPerSecond": 18.3,
                    "totalMs": 4200.0,
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(benchmark_service, "_load_live_slot_metric", lambda config=None: None)
    monkeypatch.setattr(
        benchmark_service,
        "_load_run_state",
        lambda config=None: {
            "runId": "",
            "status": "idle",
            "mode": "selected",
            "batteryId": "default",
            "batteryName": "Default battery",
            "scenarioId": "",
            "scenarioName": "",
            "currentScenarioId": "",
            "currentScenarioName": "",
            "currentIndex": 0,
            "totalScenarios": 0,
            "percent": 0,
            "startedAt": "",
            "finishedAt": "",
            "message": "Benchmark nije pokrenut.",
            "scenarioStatuses": [],
        },
    )

    payload = benchmark_service.load_benchmark_summary()

    assert payload["liveCurrent"] is None
    assert payload["liveState"] == {
        "status": "recent-benchmark",
        "hasLiveSignal": False,
        "reason": "Runtime trenutno nema aktivan live throughput signal. Prikazujem poslednji benchmark throughput kao referencu dok nema novog live saobraćaja.",
    }
    assert payload["telemetry"]["liveNowTokensPerSecond"] == 18.3
    assert payload["telemetry"]["flowState"] == "recent-benchmark"
    assert payload["telemetry"]["flowStateLabel"] == "skorašnji benchmark"
    assert payload["telemetry"]["lastUpdate"] == (now - timedelta(minutes=4)).isoformat()


def test_load_benchmark_summary_does_not_treat_stale_live_history_as_active_signal(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import benchmark_service

    install_root = tmp_path / "install-root"
    now = datetime.now(timezone.utc)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_runtime_endpoint_config(install_root)
    _write_active_model_config(install_root)
    _write_settings_config(install_root)

    config = get_config()
    config.control_center_config_root.mkdir(parents=True, exist_ok=True)
    config.benchmark_live_history_path.write_text(
        json.dumps(
            [
                {
                    "measuredAt": (now - timedelta(minutes=5)).isoformat(),
                    "label": "opencode-live",
                    "promptTokensPerSecond": None,
                    "completionTokensPerSecond": 22.4,
                    "totalTokensPerSecond": 22.4,
                    "totalMs": 5000.0,
                    "signature": "opencode-live:stale-sample",
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(benchmark_service, "_load_live_slot_metric", lambda config=None: None)

    payload = benchmark_service.load_benchmark_summary()

    assert payload["liveCurrent"] is None
    assert payload["liveState"] == {
        "status": "idle",
        "hasLiveSignal": False,
        "reason": "Runtime trenutno nema aktivan throughput signal. Pokreni benchmark ili OpenCode zahtev da bi se live tok/s pojavio.",
    }
    assert payload["telemetry"]["liveNowTokensPerSecond"] is None
    assert payload["telemetry"]["flowState"] == "quiet"


def test_benchmark_workers_persist_richer_run_metadata(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import benchmark_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_runtime_endpoint_config(install_root)
    _write_active_model_config(install_root, filename="Qwen3.6-35B-A3B-UD-IQ2_M.gguf")
    _write_settings_config(install_root, profile="balanced", context=262144, output_tokens=8192, thinking_mode="mid")

    config = get_config()
    config.control_center_config_root.mkdir(parents=True, exist_ok=True)
    benchmark_service._save_run_state(
        config,
        {
            "runId": "bench-meta",
            "status": "queued",
            "mode": "selected",
            "batteryId": "default",
            "batteryName": "Default battery",
            "scenarioId": "short",
            "scenarioName": "Short",
            "currentScenarioId": "short",
            "currentScenarioName": "Short",
            "currentIndex": 1,
            "totalScenarios": 1,
            "percent": 0,
            "startedAt": "2026-05-25T00:00:00+00:00",
            "finishedAt": "",
            "message": "Pokrećem benchmark scenario: Short",
            "scenarioStatuses": [
                {
                    "scenarioId": "short",
                    "scenarioName": "Short",
                    "status": "queued",
                    "summary": "čeka pokretanje.",
                }
            ],
        },
    )
    monkeypatch.setattr(
        benchmark_service,
        "_execute_benchmark_prompt",
        lambda *args, **kwargs: {
            "status": "ok",
            "summary": "Benchmark scenario je završen.",
            "metric": {
                "measuredAt": "2026-05-25T00:00:10+00:00",
                "label": "benchmark-short",
                "promptTokensPerSecond": 11.0,
                "completionTokensPerSecond": 22.0,
                "totalTokensPerSecond": 18.0,
                "totalMs": 1400.0,
            },
        },
    )

    benchmark_service._run_selected_worker(
        config,
        "bench-meta",
        {
            "id": "short",
            "name": "Short",
            "prompt": "Reply with exactly OK",
        },
    )

    saved_runs = benchmark_service._load_saved_runs(config)
    assert saved_runs[0]["modelId"] == "recommended-6gb"
    assert saved_runs[0]["modelLabel"] == "Qwen3.6-35B-A3B-UD-IQ2_M.gguf"
    assert saved_runs[0]["runtime"] == "llama.cpp"
    assert saved_runs[0]["runtimeLabel"] == "llama.cpp"
    assert saved_runs[0]["context"] == 262144
    assert saved_runs[0]["outputTokens"] == 8192
    assert saved_runs[0]["profile"] == "balanced"
    assert saved_runs[0]["thinkingMode"] == "mid"
    assert saved_runs[0]["currentMetric"]["environment"]["modelLabel"] == "Qwen3.6-35B-A3B-UD-IQ2_M.gguf"


def test_load_benchmark_compare_summarizes_selected_runs(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services.benchmark_service import (
        load_benchmark_compare,
    )

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_runtime_endpoint_config(install_root)
    _write_active_model_config(install_root)
    _write_settings_config(install_root)

    config = get_config()
    config.control_center_config_root.mkdir(parents=True, exist_ok=True)
    config.benchmark_saved_runs_path.write_text(
        json.dumps(
            [
                {
                    "runId": "run-fast",
                    "mode": "selected",
                    "batteryName": "Default battery",
                    "scenarioName": "Short",
                    "modelId": "recommended-6gb",
                    "runtime": "llama.cpp",
                    "status": "done",
                    "startedAt": "2026-05-25T08:00:00+00:00",
                    "finishedAt": "2026-05-25T08:00:30+00:00",
                    "currentMetric": {
                        "measuredAt": "2026-05-25T08:00:20+00:00",
                        "label": "benchmark-short",
                        "promptTokensPerSecond": 20.0,
                        "completionTokensPerSecond": 40.0,
                        "totalTokensPerSecond": 31.0,
                        "totalMs": 1200.0,
                    },
                },
                {
                    "runId": "run-battery",
                    "mode": "battery",
                    "batteryName": "Daily battery",
                    "scenarioName": "",
                    "modelId": "recommended-6gb",
                    "runtime": "llama.cpp",
                    "status": "done",
                    "startedAt": "2026-05-25T09:00:00+00:00",
                    "finishedAt": "2026-05-25T09:03:00+00:00",
                    "scenarioResults": [
                        {
                            "scenarioId": "short",
                            "scenarioName": "Short",
                            "status": "done",
                            "summary": "ok",
                            "metric": {
                                "measuredAt": "2026-05-25T09:00:20+00:00",
                                "label": "benchmark-short",
                                "promptTokensPerSecond": 10.0,
                                "completionTokensPerSecond": 30.0,
                                "totalTokensPerSecond": 22.0,
                                "totalMs": 1700.0,
                            },
                        },
                        {
                            "scenarioId": "medium",
                            "scenarioName": "Medium",
                            "status": "done",
                            "summary": "ok",
                            "metric": {
                                "measuredAt": "2026-05-25T09:01:20+00:00",
                                "label": "benchmark-medium",
                                "promptTokensPerSecond": 12.0,
                                "completionTokensPerSecond": 28.0,
                                "totalTokensPerSecond": 20.0,
                                "totalMs": 1900.0,
                            },
                        },
                    ],
                },
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = load_benchmark_compare(["run-fast", "run-battery"])

    assert payload["status"] == "ok"
    assert payload["runIds"] == ["run-fast", "run-battery"]
    assert payload["rows"][0]["runId"] == "run-fast"
    assert payload["rows"][0]["runtimeLabel"] == "llama.cpp"
    assert payload["rows"][1]["scenarioCount"] == 2
    assert payload["comparison"]["totalTokensPerSecond"]["bestRunId"] == "run-fast"
    assert payload["comparison"]["totalMs"]["bestRunId"] == "run-fast"
    assert payload["comparison"]["completionTokensPerSecond"]["average"] == 34.5


def test_load_benchmark_compare_rejects_missing_run_ids(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services.benchmark_service import (
        load_benchmark_compare,
    )

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_runtime_endpoint_config(install_root)
    _write_active_model_config(install_root)
    _write_settings_config(install_root)

    config = get_config()
    config.control_center_config_root.mkdir(parents=True, exist_ok=True)
    config.benchmark_saved_runs_path.write_text(
        json.dumps(
            [
                {
                    "runId": "run-fast",
                    "mode": "selected",
                    "batteryName": "Default battery",
                    "scenarioName": "Short",
                    "modelId": "recommended-6gb",
                    "runtime": "llama.cpp",
                    "status": "done",
                    "startedAt": "2026-05-25T08:00:00+00:00",
                    "finishedAt": "2026-05-25T08:00:30+00:00",
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = load_benchmark_compare(["run-fast", "missing-run"])

    assert payload["status"] == "error"
    assert payload["summary"] == "Benchmark run nije pronađen: missing-run"


def test_save_load_and_restore_benchmark_batteries(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import benchmark_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    saved = benchmark_service.save_battery(
        "Custom stress",
        [
            {
                "id": "stress",
                "name": "Stress",
                "prompt": "Explain local inference in 8 bullet points.",
                "description": "stress prompt",
            }
        ],
    )
    assert saved["status"] == "ok"
    battery_id = saved["battery"]["id"]

    loaded = benchmark_service.load_battery_selection(battery_id)
    assert loaded["status"] == "ok"
    assert loaded["battery"]["id"] == battery_id

    batteries_payload = benchmark_service.list_batteries()
    assert any(item["id"] == battery_id for item in batteries_payload["batteries"])
    assert batteries_payload["selectedBattery"]["id"] == battery_id

    restored = benchmark_service.restore_default_batteries()
    assert restored["status"] == "ok"
    assert restored["battery"]["id"] == "default"


def test_start_selected_benchmark_queues_run_state_and_returns_action_id(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import benchmark_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_runtime_endpoint_config(install_root)
    _write_active_model_config(install_root)

    monkeypatch.setattr(
        benchmark_service,
        "ensure_runtime_ready",
        lambda config=None: {"status": "ok", "summary": "Runtime spreman."},
    )

    started_threads: list[object] = []

    class FakeThread:
        def __init__(self, *, target, args, daemon):
            self.target = target
            self.args = args
            self.daemon = daemon
            started_threads.append(self)

        def start(self):
            return None

    monkeypatch.setattr(benchmark_service.threading, "Thread", FakeThread)

    result = benchmark_service.start_selected_benchmark("short")

    assert result["status"] == "accepted"
    assert result["runId"].startswith("bench-")
    assert started_threads

    run_state = benchmark_service.load_benchmark_run_status()
    assert run_state["status"] == "queued"
    assert run_state["scenarioId"] == "short"
    assert run_state["percent"] == 0
