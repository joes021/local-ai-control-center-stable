from pathlib import Path

from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.main import app


def test_tuning_lab_summary_route_returns_installer_managed_payload(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    client = TestClient(app)
    response = client.get("/api/tuning-lab")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert [slot["id"] for slot in payload["slots"]] == ["baseline", "recommended", "custom"]


def test_tuning_lab_run_status_route_returns_active_run_payload(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    state_path = install_root / "config" / "control-center" / "tuning-lab-run-state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        """
        {
          "activeRun": {
            "runId": "tune-001",
            "status": "running",
            "goal": "code"
          },
          "queue": []
        }
        """.strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    client = TestClient(app)
    response = client.get("/api/tuning-lab/run-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["runId"] == "tune-001"
    assert payload["status"] == "running"
    assert payload["goal"] == "code"


def test_tuning_lab_history_route_supports_pagination(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    history_path = install_root / "config" / "control-center" / "tuning-lab-history.json"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        """
        [
          {"runId": "run-1", "status": "done"},
          {"runId": "run-2", "status": "failed"}
        ]
        """.strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    client = TestClient(app)
    response = client.get("/api/tuning-lab/history?page=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["historyPage"] == 1
    assert payload["historyTotalItems"] == 2
    assert [item["runId"] for item in payload["history"]] == ["run-1", "run-2"]


def test_tuning_lab_queue_route_accepts_experiment_payload(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(tuning_lab_service, "_ensure_tuning_worker", lambda config=None: None)

    client = TestClient(app)
    response = client.post(
        "/api/tuning-lab/queue",
        json={
            "name": "Demo",
            "goal": "code",
            "taskPrompt": "Implement something small",
            "workingDirectory": str(tmp_path),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["runId"].startswith("tuning-")


def test_tuning_lab_apply_export_and_import_routes_work(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(tuning_lab_service, "_ensure_tuning_worker", lambda config=None: None)
    history_path = install_root / "config" / "control-center" / "tuning-lab-history.json"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        """
        [
          {
            "runId": "run-apply",
            "goal": "code",
            "suggestedWinnerSlotId": "recommended",
            "slots": [
              {
                "id": "recommended",
                "label": "Recommended",
                "settingsPatch": {
                  "profile": "speed",
                  "context": 131072,
                  "outputTokens": 4096,
                  "thinkingMode": "low",
                  "temperature": 0.2,
                  "topK": 20,
                  "topP": 0.9,
                  "minP": 0.0,
                  "repeatPenalty": 1.0,
                  "repeatLastN": 64,
                  "presencePenalty": 0.0,
                  "frequencyPenalty": 0.0,
                  "seed": 7
                }
              }
            ]
          }
        ]
        """.strip(),
        encoding="utf-8",
    )
    settings_path = install_root / "config" / "control-center" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        """
        {
          "profile": "balanced",
          "themeId": "dark-chocolate",
          "workflowPresetId": "research",
          "context": 262144,
          "outputTokens": 8192,
          "workingDirectory": "__WORKDIR__",
          "thinkingMode": "mid",
          "temperature": 0.8,
          "topK": 40,
          "topP": 0.95,
          "minP": 0.05,
          "repeatPenalty": 1.0,
          "repeatLastN": 64,
          "presencePenalty": 0.0,
          "frequencyPenalty": 0.0,
          "seed": -1,
          "buildSteps": 140,
          "planSteps": 100,
          "generalSteps": 110,
          "exploreSteps": 80,
          "accessMode": "local-only",
          "securityMode": "strict",
          "capabilityMode": "confirm-commands",
          "webSearchMode": "off",
          "webSearchProvider": "duckduckgo",
          "webSearchBaseUrlMode": "managed-local",
          "webSearchBaseUrl": "",
          "webSearchMaxResults": 5,
          "webSearchTimeoutSeconds": 20,
          "webSearchPromptPrefix": "/web"
        }
        """.replace("__WORKDIR__", str(tmp_path).replace("\\", "\\\\")),
        encoding="utf-8",
    )

    client = TestClient(app)

    export_response = client.post("/api/tuning-lab/export", json={"runId": "run-apply"})
    assert export_response.status_code == 200
    assert export_response.json()["experiment"]["runId"] == "run-apply"

    apply_response = client.post("/api/tuning-lab/apply-winner", json={"runId": "run-apply"})
    assert apply_response.status_code == 200
    assert apply_response.json()["status"] == "ok"

    import_response = client.post(
        "/api/tuning-lab/import-snippet",
        json={"snippet": "--temp 0.6 --top-k 12 --top-p 0.88 --seed 77"},
    )
    assert import_response.status_code == 200
    import_payload = import_response.json()
    assert import_payload["status"] == "ok"
    assert import_payload["settingsPatch"]["temperature"] == 0.6
    assert import_payload["settingsPatch"]["topK"] == 12
