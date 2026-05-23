import json
from pathlib import Path

from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.main import app


def _write_opencode_fixture(install_root: Path) -> None:
    opencode_root = install_root / "tools" / "opencode"
    opencode_root.mkdir(parents=True, exist_ok=True)
    (opencode_root / "opencode.exe").write_text("opencode", encoding="utf-8")
    config_root = install_root / "config" / "opencode"
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "managed-config.json").write_text(
        json.dumps(
            {
                "model": "local-lacc/recommended-6gb",
                "providers": {"local-lacc": {"options": {"baseURL": "http://127.0.0.1:39281/v1"}}},
            }
        ),
        encoding="utf-8",
    )


def test_opencode_status_route_reports_packaged_installation(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_opencode_fixture(install_root)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.detect_opencode_instances",
        lambda executable_path: [],
    )

    client = TestClient(app)
    response = client.get("/api/opencode/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["active"] is False
    assert payload["instanceCount"] == 0
    assert payload["configExists"] is True
    assert payload["configPath"].endswith("config\\opencode\\managed-config.json")
    assert payload["executablePath"].endswith("tools\\opencode\\opencode.exe")
    assert payload["profile"] == "balanced"


def test_opencode_open_route_spawns_packaged_executable(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_opencode_fixture(install_root)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    captured: dict[str, object] = {}

    class FakeProcess:
        pid = 8123

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.subprocess.Popen",
        fake_popen,
    )

    client = TestClient(app)
    response = client.post("/api/opencode/open", json={"profile": "balanced"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "OpenCode je pokrenut" in payload["summary"]
    assert captured["command"][0].endswith("tools\\opencode\\opencode.exe")
    assert captured["kwargs"]["env"]["OPENCODE_CONFIG"].endswith(
        "config\\opencode\\managed-config.json"
    )


def test_opencode_steps_and_settings_routes_persist_panel_managed_values(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_opencode_fixture(install_root)
    model_root = install_root / "models" / "recommended-6gb"
    model_root.mkdir(parents=True, exist_ok=True)
    (model_root / "gemma-4-E4B-it-Q4_K_M.gguf").write_text("model", encoding="utf-8")
    config_root = install_root / "config"
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "active-model.json").write_text(
        json.dumps(
            {
                "model_id": "recommended-6gb",
                "model_path": str(model_root / "gemma-4-E4B-it-Q4_K_M.gguf"),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.detect_opencode_instances",
        lambda executable_path: [],
    )

    client = TestClient(app)
    schema_response = client.get("/api/opencode/steps")
    assert schema_response.status_code == 200
    schema_payload = schema_response.json()
    assert schema_payload["builtInPresets"]
    assert schema_payload["currentSteps"]["buildSteps"] == 140

    apply_response = client.post(
        "/api/opencode/settings/apply",
        json={
            "profile": "speed",
            "context": 131072,
            "outputTokens": 4096,
            "workingDirectory": str(tmp_path / "workspace"),
            "buildSteps": 200,
            "planSteps": 150,
            "generalSteps": 120,
            "exploreSteps": 90,
            "securityMode": "open",
            "capabilityMode": "auto-commands",
        },
    )
    assert apply_response.status_code == 200
    assert apply_response.json()["status"] == "ok"

    preset_response = client.post(
        "/api/opencode/steps/presets/save",
        json={
            "name": "My steps",
            "steps": {
                "buildSteps": 200,
                "planSteps": 150,
                "generalSteps": 120,
                "exploreSteps": 90,
            },
        },
    )
    assert preset_response.status_code == 200
    assert preset_response.json()["status"] == "ok"

    status_response = client.get("/api/opencode/status")
    status_payload = status_response.json()
    assert status_payload["workingDirectory"] == str(tmp_path / "workspace")
    assert status_payload["securityMode"] == "open"
    assert status_payload["capabilityMode"] == "auto-commands"
    assert status_payload["buildSteps"] == 200
    assert status_payload["profile"] == "speed"

    updated_schema = client.get("/api/opencode/steps").json()
    assert len(updated_schema["userPresets"]) == 1
    preset_id = updated_schema["userPresets"][0]["id"]

    delete_response = client.post(
        "/api/opencode/steps/presets/delete",
        json={"presetId": preset_id},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "ok"
