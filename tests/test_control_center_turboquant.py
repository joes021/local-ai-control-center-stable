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


def test_turboquant_schema_route_exposes_recommended_models_and_persists_user_preset(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_active_model_config(install_root)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    client = TestClient(app)
    initial = client.get("/api/settings/turboquant")
    assert initial.status_code == 200
    initial_payload = initial.json()
    assert initial_payload["builtInPresets"]
    assert initial_payload["recommendedModels"]
    assert initial_payload["currentConfig"]["context"] == 131072
    assert initial_payload["currentConfig"]["runtimePreference"] == "turboquant"

    config_response = client.post(
        "/api/settings/turboquant-config",
        json={
            "context": 65536,
            "ctk": "turbo4",
            "ctv": "turbo3",
            "ncmoe": 30,
            "flashAttention": True,
            "mlock": False,
            "mmapMode": "mmap",
            "runtimePreference": "llama.cpp",
        },
    )
    assert config_response.status_code == 200
    assert config_response.json()["status"] == "ok"

    preset_response = client.post(
        "/api/settings/turboquant-presets/save",
        json={
            "name": "My preset",
            "description": "Opis",
            "targetModelPattern": "qwen*",
            "notes": "Napomena",
            "settings": {
                "context": 65536,
                "ctk": "turbo4",
                "ctv": "turbo3",
                "ncmoe": 30,
                "flashAttention": True,
                "mlock": False,
                "mmapMode": "mmap",
                "runtimePreference": "llama.cpp",
            },
        },
    )
    assert preset_response.status_code == 200
    assert preset_response.json()["status"] == "ok"

    reloaded = client.get("/api/settings/turboquant")
    reloaded_payload = reloaded.json()
    assert reloaded_payload["currentConfig"]["context"] == 65536
    assert reloaded_payload["currentConfig"]["runtimePreference"] == "llama.cpp"
    assert len(reloaded_payload["userPresets"]) == 1

    preset_id = reloaded_payload["userPresets"][0]["id"]
    delete_response = client.post(
        "/api/settings/turboquant-presets/delete",
        json={"presetId": preset_id},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "ok"

    final_payload = client.get("/api/settings/turboquant").json()
    assert final_payload["userPresets"] == []
