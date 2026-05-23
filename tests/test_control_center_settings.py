import json
from pathlib import Path

from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.main import app


def _write_active_model_config(install_root: Path) -> None:
    model_path = install_root / "models" / "recommended-6gb" / "gemma-4-E4B-it-Q4_K_M.gguf"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text("model", encoding="utf-8")
    config_root = install_root / "config"
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "active-model.json").write_text(
        json.dumps(
            {
                "model_id": "recommended-6gb",
                "model_path": str(model_path),
            }
        ),
        encoding="utf-8",
    )


def test_settings_route_persists_global_defaults_and_model_override(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_active_model_config(install_root)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    client = TestClient(app)
    initial = client.get("/api/settings")
    assert initial.status_code == 200
    assert initial.json()["settingsScope"] == "global"
    assert initial.json()["activeModelId"] == "recommended-6gb"

    response = client.post(
        "/api/settings/apply",
        json={
            "profile": "speed",
            "context": 65536,
            "outputTokens": 2048,
            "workingDirectory": str(tmp_path / "workspace"),
            "thinkingMode": "low",
            "buildSteps": 1,
            "planSteps": 1,
            "generalSteps": 1,
            "exploreSteps": 1,
            "settingsScope": "global",
            "activeModelId": "recommended-6gb",
            "activeModelLabel": "gemma-4-E4B-it-Q4_K_M.gguf",
            "modelOverrideExists": False,
            "accessMode": "local-only",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    reloaded = client.get("/api/settings")
    payload = reloaded.json()
    assert payload["profile"] == "speed"
    assert payload["context"] == 65536
    assert payload["outputTokens"] == 2048
    assert payload["workingDirectory"] == str(tmp_path / "workspace")
    assert payload["thinkingMode"] == "low"
    assert payload["buildSteps"] == 40
    assert payload["planSteps"] == 30
    assert payload["settingsScope"] == "global"

    override_response = client.post(
        "/api/settings/apply",
        json={
            "profile": "video",
            "context": 131072,
            "outputTokens": 4096,
            "workingDirectory": str(tmp_path / "workspace-override"),
            "thinkingMode": "high",
            "buildSteps": 1,
            "planSteps": 1,
            "generalSteps": 1,
            "exploreSteps": 1,
            "settingsScope": "model",
            "activeModelId": "recommended-6gb",
            "activeModelLabel": "gemma-4-E4B-it-Q4_K_M.gguf",
            "modelOverrideExists": False,
            "accessMode": "local-only",
        },
    )
    assert override_response.status_code == 200
    assert override_response.json()["status"] == "ok"

    reloaded_override = client.get("/api/settings")
    override_payload = reloaded_override.json()
    assert override_payload["settingsScope"] == "model"
    assert override_payload["modelOverrideExists"] is True
    assert override_payload["profile"] == "video"
    assert override_payload["context"] == 131072
    assert override_payload["workingDirectory"] == str(tmp_path / "workspace-override")
    assert override_payload["buildSteps"] == 160
