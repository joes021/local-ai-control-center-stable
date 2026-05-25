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
    assert initial.json()["selectedSettingsProfileId"] == "balanced"
    assert [item["id"] for item in initial.json()["builtInSettingsProfiles"]] == [
        "balanced",
        "speed",
        "video",
    ]
    assert initial.json()["userSettingsProfiles"] == []
    assert initial.json()["webSearchMode"] == "off"
    assert initial.json()["webSearchProvider"] == "searxng"
    assert initial.json()["webSearchBaseUrl"] == "http://127.0.0.1:8080"
    assert initial.json()["webSearchMaxResults"] == 5
    assert initial.json()["webSearchTimeoutSeconds"] == 20
    assert initial.json()["webSearchPromptPrefix"] == "/web"

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
            "webSearchMode": "on-demand",
            "webSearchProvider": "searxng",
            "webSearchBaseUrl": "http://127.0.0.1:18080",
            "webSearchMaxResults": 7,
            "webSearchTimeoutSeconds": 12,
            "webSearchPromptPrefix": "!web",
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
    assert payload["selectedSettingsProfileId"] == "custom"
    assert payload["webSearchMode"] == "on-demand"
    assert payload["webSearchProvider"] == "searxng"
    assert payload["webSearchBaseUrl"] == "http://127.0.0.1:18080"
    assert payload["webSearchMaxResults"] == 7
    assert payload["webSearchTimeoutSeconds"] == 12
    assert payload["webSearchPromptPrefix"] == "!web"

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
            "webSearchMode": "always",
            "webSearchProvider": "searxng",
            "webSearchBaseUrl": "http://127.0.0.1:9999",
            "webSearchMaxResults": 2,
            "webSearchTimeoutSeconds": 4,
            "webSearchPromptPrefix": "/browser",
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
    assert override_payload["webSearchMode"] == "on-demand"
    assert override_payload["webSearchBaseUrl"] == "http://127.0.0.1:18080"
    assert override_payload["webSearchMaxResults"] == 7
    assert override_payload["webSearchTimeoutSeconds"] == 12
    assert override_payload["webSearchPromptPrefix"] == "!web"


def test_settings_route_saves_and_deletes_custom_settings_profiles(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_active_model_config(install_root)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    client = TestClient(app)

    save_response = client.post(
        "/api/settings/profiles/save",
        json={
            "name": "My deep profile",
            "settings": {
                "profile": "video",
                "context": 65536,
                "outputTokens": 4096,
                "workingDirectory": str(tmp_path / "deep-workspace"),
                "thinkingMode": "high",
                "accessMode": "tailscale",
            },
        },
    )
    assert save_response.status_code == 200
    assert save_response.json()["status"] == "ok"

    payload = client.get("/api/settings").json()
    assert len(payload["userSettingsProfiles"]) == 1
    custom_profile = payload["userSettingsProfiles"][0]
    assert custom_profile["name"] == "My deep profile"
    assert custom_profile["summary"] == "video | 64k ctx | 4k out | high"
    assert custom_profile["settings"]["profile"] == "video"
    assert custom_profile["settings"]["context"] == 65536
    assert custom_profile["settings"]["outputTokens"] == 4096
    assert custom_profile["settings"]["workingDirectory"] == str(tmp_path / "deep-workspace")
    assert custom_profile["settings"]["thinkingMode"] == "high"
    assert custom_profile["settings"]["buildSteps"] == 160
    assert custom_profile["settings"]["accessMode"] == "tailscale"
    assert "webSearchMode" not in custom_profile["settings"]

    apply_response = client.post(
        "/api/settings/apply",
        json={
            **custom_profile["settings"],
            "settingsScope": "global",
            "activeModelId": "recommended-6gb",
            "activeModelLabel": "gemma-4-E4B-it-Q4_K_M.gguf",
            "modelOverrideExists": False,
        },
    )
    assert apply_response.status_code == 200
    assert apply_response.json()["status"] == "ok"

    matched = client.get("/api/settings").json()
    assert matched["selectedSettingsProfileId"] == custom_profile["id"]
    assert matched["selectedSettingsProfileName"] == "My deep profile"

    delete_response = client.post(
        "/api/settings/profiles/delete",
        json={"profileId": custom_profile["id"]},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "ok"

    deleted = client.get("/api/settings").json()
    assert deleted["userSettingsProfiles"] == []
    assert deleted["selectedSettingsProfileId"] == "custom"
