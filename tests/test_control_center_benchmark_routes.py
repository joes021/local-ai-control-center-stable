import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.main import app
from local_ai_control_center_installer.control_center_backend.routes import benchmark as benchmark_routes


def _write_runtime_endpoint_config(install_root: Path, *, port: int = 39281) -> None:
    config_root = install_root / "config"
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "runtime-endpoint.json").write_text(
        json.dumps({"port": port, "base_url": f"http://127.0.0.1:{port}"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_benchmark_summary_route_returns_installer_managed_payload(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    now = datetime.now(timezone.utc)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_runtime_endpoint_config(install_root)

    config_root = install_root / "config" / "control-center"
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "benchmark-history.json").write_text(
        json.dumps(
            [
                {
                    "measuredAt": (now - timedelta(seconds=10)).isoformat(),
                    "label": "benchmark-short",
                    "promptTokensPerSecond": 18.0,
                    "completionTokensPerSecond": 28.0,
                    "totalTokensPerSecond": 23.0,
                    "totalMs": 1500.0,
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    client = TestClient(app)
    response = client.get("/api/benchmark")

    assert response.status_code == 200
    payload = response.json()
    assert payload["historyCount"] == 1
    assert payload["current"]["label"] == "benchmark-short"
    assert "averages" in payload
    assert "activeRun" in payload


def test_benchmark_run_status_route_returns_active_run_payload(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_runtime_endpoint_config(install_root)

    config_root = install_root / "config" / "control-center"
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "benchmark-run-state.json").write_text(
        json.dumps(
            {
                "runId": "bench-123",
                "status": "running",
                "mode": "battery",
                "batteryId": "default",
                "batteryName": "Default battery",
                "scenarioId": "short",
                "scenarioName": "Short",
                "currentScenarioId": "short",
                "currentScenarioName": "Short",
                "currentIndex": 1,
                "totalScenarios": 3,
                "percent": 33,
                "startedAt": "2026-05-24T10:00:00+00:00",
                "finishedAt": "",
                "message": "Scenario radi.",
                "scenarioStatuses": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    client = TestClient(app)
    response = client.get("/api/benchmark/run-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["runId"] == "bench-123"
    assert payload["status"] == "running"
    assert payload["mode"] == "battery"


def test_benchmark_battery_routes_save_and_restore_defaults(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_runtime_endpoint_config(install_root)

    client = TestClient(app)

    save_response = client.post(
        "/api/benchmark/batteries/save",
        json={
            "name": "API battery",
            "scenarios": [
                {
                    "id": "api-short",
                    "name": "API Short",
                    "prompt": "Reply with exactly OK",
                    "description": "api test",
                }
            ],
        },
    )
    assert save_response.status_code == 200
    saved_payload = save_response.json()
    assert saved_payload["status"] == "ok"
    battery_id = saved_payload["battery"]["id"]

    load_response = client.post("/api/benchmark/batteries/load", json={"batteryId": battery_id})
    assert load_response.status_code == 200
    assert load_response.json()["battery"]["id"] == battery_id

    restore_response = client.post("/api/benchmark/batteries/restore-defaults")
    assert restore_response.status_code == 200
    assert restore_response.json()["battery"]["id"] == "default"


def test_benchmark_run_and_clear_routes_delegate_to_backend_actions(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        benchmark_routes,
        "start_selected_benchmark",
        lambda scenario_id: {
            "status": "accepted",
            "action": "benchmark-run-selected",
            "summary": f"selected:{scenario_id}",
            "details": {"returncode": 0, "stdout": "", "stderr": ""},
            "runId": "bench-selected",
        },
    )
    monkeypatch.setattr(
        benchmark_routes,
        "start_battery_benchmark",
        lambda battery_id: {
            "status": "accepted",
            "action": "benchmark-run-battery",
            "summary": f"battery:{battery_id}",
            "details": {"returncode": 0, "stdout": "", "stderr": ""},
            "runId": "bench-battery",
        },
    )
    monkeypatch.setattr(
        benchmark_routes,
        "clear_benchmark_history",
        lambda: {
            "status": "ok",
            "action": "benchmark-clear-history",
            "summary": "cleared",
            "details": {"returncode": 0, "stdout": "", "stderr": ""},
        },
    )

    selected_response = client.post("/api/benchmark/run-selected", json={"scenarioId": "short"})
    assert selected_response.status_code == 200
    assert selected_response.json()["summary"] == "selected:short"

    battery_response = client.post("/api/benchmark/run-battery", json={"batteryId": "default"})
    assert battery_response.status_code == 200
    assert battery_response.json()["summary"] == "battery:default"

    clear_response = client.post("/api/benchmark/clear-history")
    assert clear_response.status_code == 200
    assert clear_response.json()["summary"] == "cleared"


def test_benchmark_compare_route_returns_selected_runs(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        benchmark_routes,
        "load_benchmark_compare",
        lambda run_ids: {
            "status": "ok",
            "summary": "2 benchmark run-a su spremna za poredjenje.",
            "runIds": run_ids,
            "runs": [{"runId": "run-a"}, {"runId": "run-b"}],
            "rows": [{"runId": "run-a"}, {"runId": "run-b"}],
            "comparison": {
                "totalTokensPerSecond": {"bestRunId": "run-a", "bestValue": 31.0, "average": 27.0}
            },
        },
    )

    response = client.get("/api/benchmark/compare", params=[("runIds", "run-a"), ("runIds", "run-b")])

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["runIds"] == ["run-a", "run-b"]


def test_benchmark_compare_route_rejects_missing_run_ids(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        benchmark_routes,
        "load_benchmark_compare",
        lambda run_ids: {
            "status": "error",
            "summary": "Benchmark run nije pronadjen: missing-run",
        },
    )

    response = client.get("/api/benchmark/compare", params=[("runIds", "run-a"), ("runIds", "missing-run")])

    assert response.status_code == 404
    assert response.json()["detail"] == "Benchmark run nije pronadjen: missing-run"


def test_benchmark_export_route_returns_json_and_csv(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        benchmark_routes,
        "export_benchmark_runs",
        lambda export_format, run_ids=None: (
            {
                "exportedAt": "2026-05-25T10:00:00+00:00",
                "runCount": len(run_ids or []),
                "runs": [{"runId": "run-a"}],
            }
            if export_format == "json"
            else "runId,mode,status\nrun-a,selected,done\n"
        ),
    )

    json_response = client.get("/api/benchmark/export", params=[("format", "json"), ("runIds", "run-a")])
    assert json_response.status_code == 200
    assert json_response.json()["runCount"] == 1

    csv_response = client.get("/api/benchmark/export", params=[("format", "csv"), ("runIds", "run-a")])
    assert csv_response.status_code == 200
    assert csv_response.text.startswith("runId,mode,status")
    assert csv_response.headers["content-type"].startswith("text/csv")
