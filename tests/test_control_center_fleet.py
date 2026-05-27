from pathlib import Path

from local_ai_control_center_installer.control_center_backend.config import get_config


def test_control_center_config_exposes_fleet_registry_path(tmp_path: Path, monkeypatch):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    config = get_config()

    assert config.fleet_registry_path == install_root / "config" / "control-center" / "fleet-machines.json"


def test_fleet_service_add_refresh_and_remove_machine(tmp_path: Path, monkeypatch):
    from local_ai_control_center_installer.control_center_backend.services import fleet_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    def fake_fetch(base_url: str, path: str) -> dict[str, object]:
        if path == "/api/status":
            return {
                "version": "0.4.38",
                "activeModel": "Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf",
                "activeRuntimeLabel": "turboquant",
                "runtimeLiveStatus": "started",
                "runtimeSummary": "healthy",
                "uiUrl": f"{base_url}/",
            }
        if path == "/api/server/status":
            return {
                "runtime": "turboquant",
                "status": "started",
                "health": "ok",
            }
        if path == "/api/benchmark":
            return {
                "telemetry": {
                    "input24h": 50000,
                    "output24h": 25000,
                    "liveNowTokensPerSecond": 22.4,
                    "flowStateLabel": "active generation",
                }
            }
        if path == "/health":
            return {"status": "ok"}
        raise AssertionError(f"Unexpected fleet path: {path}")

    monkeypatch.setattr(fleet_service, "_fetch_remote_json", fake_fetch)

    add_result = fleet_service.add_fleet_machine("Workstation", "http://192.0.2.10:3210")
    assert add_result["status"] == "ok"
    machine_id = add_result["machine"]["id"]
    assert add_result["machine"]["snapshot"]["version"] == "0.4.38"
    assert add_result["machine"]["snapshot"]["activeRuntime"] == "turboquant"

    summary = fleet_service.load_fleet_summary()
    assert summary["machineCount"] == 1
    assert summary["machines"][0]["name"] == "Workstation"
    assert summary["machines"][0]["snapshot"]["liveNowTokensPerSecond"] == 22.4

    refresh_result = fleet_service.refresh_fleet_machine(machine_id)
    assert refresh_result["status"] == "ok"
    assert refresh_result["machine"]["snapshot"]["flowStateLabel"] == "active generation"

    remove_result = fleet_service.remove_fleet_machine(machine_id)
    assert remove_result["status"] == "ok"

    final_summary = fleet_service.load_fleet_summary()
    assert final_summary["machines"] == []
