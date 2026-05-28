import json
from pathlib import Path

from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.main import app
from local_ai_control_center_installer.control_center_backend.services.settings_service import (
    LEGACY_DEFAULT_WEB_SEARCH_BASE_URL,
)


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
    assert initial.json()["webSearchBaseUrl"] == ""
    assert initial.json()["webSearchMaxResults"] == 5
    assert initial.json()["webSearchTimeoutSeconds"] == 20
    assert initial.json()["webSearchPromptPrefix"] == "/web"
    assert initial.json()["temperature"] == 0.8
    assert initial.json()["topK"] == 40
    assert initial.json()["topP"] == 0.95
    assert initial.json()["minP"] == 0.05
    assert initial.json()["repeatPenalty"] == 1.0
    assert initial.json()["repeatLastN"] == 64
    assert initial.json()["presencePenalty"] == 0.0
    assert initial.json()["frequencyPenalty"] == 0.0
    assert initial.json()["seed"] == -1
    assert initial.json()["themeId"] == "dark-chocolate"
    assert [item["id"] for item in initial.json()["availableGenerationStarters"]] == [
        "llama-cpp-default",
        "qwen-instruct",
        "qwen-thinking",
        "llama-instruct",
        "gemma-default",
        "deterministic-code",
    ]
    assert [item["id"] for item in initial.json()["availableThemes"]] == [
        "dark-chocolate",
        "light",
        "dark",
        "neon-green",
        "marine-blue",
    ]
    assert initial.json()["selectedWorkflowPresetId"] == "research"
    assert [item["id"] for item in initial.json()["availableWorkflowPresets"]] == [
        "research",
        "code",
        "low-vram",
        "long-context",
        "docs-plus-web",
        "benchmark-battery",
    ]
    code_preset = next(
        item for item in initial.json()["availableWorkflowPresets"] if item["id"] == "code"
    )
    assert code_preset["settingsPatch"]["temperature"] == 0.2
    assert code_preset["settingsPatch"]["topK"] == 20
    assert code_preset["settingsPatch"]["topP"] == 0.9
    assert code_preset["settingsPatch"]["seed"] == 7
    assert initial.json()["searchProviderStatus"]["status"] == "not-configured"

    response = client.post(
        "/api/settings/apply",
        json={
            "profile": "speed",
            "context": 65536,
            "outputTokens": 2048,
            "workingDirectory": str(tmp_path / "workspace"),
            "thinkingMode": "low",
            "temperature": 0.2,
            "topK": 40,
            "topP": 0.9,
            "minP": 0.0,
            "repeatPenalty": 1.0,
            "repeatLastN": 128,
            "presencePenalty": 0.1,
            "frequencyPenalty": 0.0,
            "seed": 42,
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
            "webSearchProvider": "duckduckgo",
            "webSearchBaseUrl": "http://127.0.0.1:18080",
            "webSearchMaxResults": 7,
            "webSearchTimeoutSeconds": 12,
            "webSearchPromptPrefix": "!web",
            "themeId": "marine-blue",
            "workflowPresetId": "low-vram",
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
    assert payload["temperature"] == 0.2
    assert payload["topK"] == 40
    assert payload["topP"] == 0.9
    assert payload["minP"] == 0.0
    assert payload["repeatPenalty"] == 1.0
    assert payload["repeatLastN"] == 128
    assert payload["presencePenalty"] == 0.1
    assert payload["frequencyPenalty"] == 0.0
    assert payload["seed"] == 42
    assert payload["buildSteps"] == 40
    assert payload["planSteps"] == 30
    assert payload["settingsScope"] == "global"
    assert payload["selectedSettingsProfileId"] == "custom"
    assert payload["webSearchMode"] == "on-demand"
    assert payload["webSearchProvider"] == "duckduckgo"
    assert payload["webSearchBaseUrl"] == ""
    assert payload["webSearchMaxResults"] == 7
    assert payload["webSearchTimeoutSeconds"] == 12
    assert payload["webSearchPromptPrefix"] == "!web"
    assert payload["themeId"] == "marine-blue"
    assert payload["selectedWorkflowPresetId"] == "low-vram"

    override_response = client.post(
        "/api/settings/apply",
        json={
            "profile": "video",
            "context": 131072,
            "outputTokens": 4096,
            "workingDirectory": str(tmp_path / "workspace-override"),
            "thinkingMode": "high",
            "temperature": 0.7,
            "topK": 20,
            "topP": 0.8,
            "minP": 0.0,
            "repeatPenalty": 1.1,
            "repeatLastN": 96,
            "presencePenalty": 0.4,
            "frequencyPenalty": 0.2,
            "seed": -1,
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
            "themeId": "light",
            "workflowPresetId": "code",
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
    assert override_payload["temperature"] == 0.7
    assert override_payload["topK"] == 20
    assert override_payload["topP"] == 0.8
    assert override_payload["minP"] == 0.0
    assert override_payload["repeatPenalty"] == 1.1
    assert override_payload["repeatLastN"] == 96
    assert override_payload["presencePenalty"] == 0.4
    assert override_payload["frequencyPenalty"] == 0.2
    assert override_payload["seed"] == -1
    assert override_payload["buildSteps"] == 160
    assert override_payload["webSearchMode"] == "on-demand"
    assert override_payload["webSearchProvider"] == "duckduckgo"
    assert override_payload["webSearchBaseUrl"] == ""
    assert override_payload["webSearchMaxResults"] == 7
    assert override_payload["webSearchTimeoutSeconds"] == 12
    assert override_payload["webSearchPromptPrefix"] == "!web"
    assert override_payload["themeId"] == "light"
    assert override_payload["selectedWorkflowPresetId"] == "code"


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
                "temperature": 0.2,
                "topK": 40,
                "topP": 0.9,
                "minP": 0.0,
                "repeatPenalty": 1.0,
                "repeatLastN": 128,
                "presencePenalty": 0.1,
                "frequencyPenalty": 0.0,
                "seed": 7,
            },
        },
    )
    assert save_response.status_code == 200
    assert save_response.json()["status"] == "ok"

    payload = client.get("/api/settings").json()
    assert len(payload["userSettingsProfiles"]) == 1
    custom_profile = payload["userSettingsProfiles"][0]
    assert custom_profile["name"] == "My deep profile"
    assert custom_profile["summary"] == "video | 64k ctx | 4k out | high | temp 0.2"
    assert custom_profile["settings"]["profile"] == "video"
    assert custom_profile["settings"]["context"] == 65536
    assert custom_profile["settings"]["outputTokens"] == 4096
    assert custom_profile["settings"]["workingDirectory"] == str(tmp_path / "deep-workspace")
    assert custom_profile["settings"]["thinkingMode"] == "high"
    assert custom_profile["settings"]["temperature"] == 0.2
    assert custom_profile["settings"]["topK"] == 40
    assert custom_profile["settings"]["topP"] == 0.9
    assert custom_profile["settings"]["minP"] == 0.0
    assert custom_profile["settings"]["repeatPenalty"] == 1.0
    assert custom_profile["settings"]["repeatLastN"] == 128
    assert custom_profile["settings"]["presencePenalty"] == 0.1
    assert custom_profile["settings"]["frequencyPenalty"] == 0.0
    assert custom_profile["settings"]["seed"] == 7
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


def test_settings_route_saves_updates_and_deletes_custom_workflow_presets(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_active_model_config(install_root)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    client = TestClient(app)

    save_response = client.post(
        "/api/settings/workflow-presets/save",
        json={
            "name": "My code deep dive",
            "summary": "Korisnički coding preset sa malo više web pomoći.",
            "badges": ["code", "custom", "web"],
            "settingsPatch": {
                "profile": "speed",
                "context": 65536,
                "outputTokens": 3072,
                "thinkingMode": "low",
                "temperature": 0.2,
                "topK": 40,
                "topP": 0.9,
                "minP": 0.0,
                "repeatPenalty": 1.0,
                "repeatLastN": 64,
                "presencePenalty": 0.0,
                "frequencyPenalty": 0.0,
                "seed": -1,
                "webSearchMode": "on-demand",
                "webSearchProvider": "duckduckgo",
            },
            "searchDefaults": {
                "provider": "duckduckgo",
                "suggestedAction": "answer",
                "queryHint": "Proveri biblioteku ili error pre odgovora.",
            },
            "knowledgeDefaults": {
                "mode": "documents-only",
                "queryHint": "Koristi lokalni kod i beleške kao prvi izvor.",
            },
            "benchmarkDefaults": {
                "batteryId": "default",
                "launchTarget": "selected",
                "runLabel": "Pokreni coding benchmark.",
            },
        },
    )
    assert save_response.status_code == 200
    assert save_response.json()["status"] == "ok"

    payload = client.get("/api/settings").json()
    workflow_presets = payload["availableWorkflowPresets"]
    assert [item["id"] for item in workflow_presets[:6]] == [
        "research",
        "code",
        "low-vram",
        "long-context",
        "docs-plus-web",
        "benchmark-battery",
    ]
    user_preset = next(item for item in workflow_presets if item["kind"] == "user")
    assert user_preset["name"] == "My code deep dive"
    assert user_preset["summary"] == "Korisnički coding preset sa malo više web pomoći."
    assert user_preset["badges"] == ["code", "custom", "web"]
    assert user_preset["settingsPatch"]["context"] == 65536
    assert user_preset["settingsPatch"]["temperature"] == 0.2
    assert user_preset["settingsPatch"]["topP"] == 0.9
    assert user_preset["searchDefaults"]["suggestedAction"] == "answer"
    assert user_preset["knowledgeDefaults"]["mode"] == "documents-only"
    assert user_preset["benchmarkDefaults"]["launchTarget"] == "selected"

    update_response = client.post(
        "/api/settings/workflow-presets/save",
        json={
            "presetId": user_preset["id"],
            "name": "My code deep dive",
            "summary": "Ažurirani coding preset sa dužim context-om.",
            "badges": ["code", "custom", "longer-context"],
            "settingsPatch": {
                "profile": "speed",
                "context": 131072,
                "outputTokens": 4096,
                "thinkingMode": "mid",
                "temperature": 0.6,
                "topK": 20,
                "topP": 0.95,
                "minP": 0.0,
                "repeatPenalty": 1.0,
                "repeatLastN": 64,
                "presencePenalty": 0.3,
                "frequencyPenalty": 0.0,
                "seed": 123,
                "webSearchMode": "on-demand",
                "webSearchProvider": "duckduckgo",
            },
            "searchDefaults": {
                "provider": "duckduckgo",
                "suggestedAction": "search",
                "queryHint": "Ažurirani search hint.",
            },
            "knowledgeDefaults": {
                "mode": "documents+web",
                "queryHint": "Spoji lokalne dokumente i web kada je potrebno.",
            },
            "benchmarkDefaults": {
                "batteryId": "default",
                "launchTarget": "battery",
                "runLabel": "Pokreni coding battery benchmark.",
            },
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "ok"

    updated_payload = client.get("/api/settings").json()
    updated_user_preset = next(
        item for item in updated_payload["availableWorkflowPresets"] if item["id"] == user_preset["id"]
    )
    assert updated_user_preset["summary"] == "Ažurirani coding preset sa dužim context-om."
    assert updated_user_preset["badges"] == ["code", "custom", "longer-context"]
    assert updated_user_preset["settingsPatch"]["context"] == 131072
    assert updated_user_preset["settingsPatch"]["temperature"] == 0.6
    assert updated_user_preset["settingsPatch"]["topP"] == 0.95
    assert updated_user_preset["knowledgeDefaults"]["mode"] == "documents+web"
    assert updated_user_preset["benchmarkDefaults"]["launchTarget"] == "battery"

    apply_response = client.post(
        "/api/settings/apply",
        json={
            "profile": "speed",
            "context": 131072,
            "outputTokens": 4096,
            "workingDirectory": str(install_root),
            "thinkingMode": "mid",
            "temperature": 0.6,
            "topK": 20,
            "topP": 0.95,
            "minP": 0.0,
            "repeatPenalty": 1.0,
            "repeatLastN": 64,
            "presencePenalty": 0.3,
            "frequencyPenalty": 0.0,
            "seed": 123,
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
            "webSearchProvider": "duckduckgo",
            "webSearchBaseUrl": "",
            "webSearchMaxResults": 5,
            "webSearchTimeoutSeconds": 20,
            "webSearchPromptPrefix": "/web",
            "themeId": "dark-chocolate",
            "workflowPresetId": user_preset["id"],
        },
    )
    assert apply_response.status_code == 200
    assert apply_response.json()["status"] == "ok"
    assert client.get("/api/settings").json()["selectedWorkflowPresetId"] == user_preset["id"]

    delete_response = client.post(
        "/api/settings/workflow-presets/delete",
        json={"presetId": user_preset["id"]},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "ok"

    deleted_payload = client.get("/api/settings").json()
    assert all(item["id"] != user_preset["id"] for item in deleted_payload["availableWorkflowPresets"])
    assert deleted_payload["selectedWorkflowPresetId"] == "research"


def test_workflow_preset_save_route_rejects_duplicate_name_and_invalid_copy(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_active_model_config(install_root)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    client = TestClient(app)

    duplicate_response = client.post(
        "/api/settings/workflow-presets/save",
        json={
            "name": "Code",
            "summary": "Pokušaj da se pregazi ugrađeni preset.",
            "badges": ["code"],
            "settingsPatch": {
                "profile": "speed",
                "context": 65536,
                "outputTokens": 4096,
                "thinkingMode": "low",
                "webSearchMode": "off",
                "webSearchProvider": "duckduckgo",
            },
            "searchDefaults": {
                "provider": "duckduckgo",
                "suggestedAction": "search",
                "queryHint": "hint",
            },
            "knowledgeDefaults": {
                "mode": "documents-only",
                "queryHint": "hint",
            },
            "benchmarkDefaults": {
                "batteryId": "default",
                "launchTarget": "selected",
                "runLabel": "Run",
            },
        },
    )
    assert duplicate_response.status_code == 200
    assert duplicate_response.json()["status"] == "error"
    assert "već postoji" in duplicate_response.json()["summary"]

    invalid_response = client.post(
        "/api/settings/workflow-presets/save",
        json={
            "name": "Moja kopija",
            "summary": "x" * 221,
            "badges": ["jedan", "dva", "tri", "četiri", "pet", "šest", "sedam"],
            "settingsPatch": {
                "profile": "speed",
                "context": 65536,
                "outputTokens": 4096,
                "thinkingMode": "low",
                "webSearchMode": "off",
                "webSearchProvider": "duckduckgo",
            },
            "searchDefaults": {
                "provider": "duckduckgo",
                "suggestedAction": "search",
                "queryHint": "hint",
            },
            "knowledgeDefaults": {
                "mode": "documents-only",
                "queryHint": "hint",
            },
            "benchmarkDefaults": {
                "batteryId": "default",
                "launchTarget": "selected",
                "runLabel": "Run",
            },
        },
    )
    assert invalid_response.status_code == 200
    assert invalid_response.json()["status"] == "error"
    assert "najviše 220 karaktera" in invalid_response.json()["summary"]


def test_settings_route_migrates_legacy_default_search_url_to_unconfigured_state(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_active_model_config(install_root)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    settings_path = install_root / "config" / "control-center" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(
            {
                "profile": "balanced",
                "context": 262144,
                "outputTokens": 8192,
                "workingDirectory": str(install_root),
                "thinkingMode": "mid",
                "buildSteps": 140,
                "planSteps": 100,
                "generalSteps": 110,
                "exploreSteps": 80,
                "accessMode": "local-only",
                "webSearchMode": "off",
                "webSearchProvider": "searxng",
                "webSearchBaseUrl": LEGACY_DEFAULT_WEB_SEARCH_BASE_URL,
                "webSearchMaxResults": 5,
                "webSearchTimeoutSeconds": 20,
                "webSearchPromptPrefix": "/web",
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(app)
    payload = client.get("/api/settings").json()

    assert payload["webSearchBaseUrl"] == ""
    assert payload["searchProviderStatus"]["status"] == "not-configured"
    assert payload["searchProviderStatus"]["configuredBaseUrl"] == ""

    save_response = client.post(
        "/api/settings/apply",
        json={
            "profile": payload["profile"],
            "context": payload["context"],
            "outputTokens": payload["outputTokens"],
            "workingDirectory": payload["workingDirectory"],
            "thinkingMode": payload["thinkingMode"],
            "buildSteps": payload["buildSteps"],
            "planSteps": payload["planSteps"],
            "generalSteps": payload["generalSteps"],
            "exploreSteps": payload["exploreSteps"],
            "settingsScope": "global",
            "activeModelId": payload["activeModelId"],
            "activeModelLabel": payload["activeModelLabel"],
            "modelOverrideExists": payload["modelOverrideExists"],
            "accessMode": payload["accessMode"],
            "webSearchMode": payload["webSearchMode"],
            "webSearchProvider": payload["webSearchProvider"],
            "webSearchBaseUrl": "http://127.0.0.1:8080",
            "webSearchMaxResults": payload["webSearchMaxResults"],
            "webSearchTimeoutSeconds": payload["webSearchTimeoutSeconds"],
            "webSearchPromptPrefix": payload["webSearchPromptPrefix"],
        },
    )
    assert save_response.status_code == 200
    assert save_response.json()["status"] == "ok"

    reloaded = client.get("/api/settings").json()
    assert reloaded["webSearchBaseUrl"] == "http://127.0.0.1:8080"
