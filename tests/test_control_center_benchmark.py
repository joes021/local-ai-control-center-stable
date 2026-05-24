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
    from local_ai_control_center_installer.control_center_backend.services.benchmark_service import (
        load_benchmark_summary,
    )

    install_root = tmp_path / "install-root"
    now = datetime.now(timezone.utc)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_runtime_endpoint_config(install_root)
    _write_active_model_config(install_root)

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
