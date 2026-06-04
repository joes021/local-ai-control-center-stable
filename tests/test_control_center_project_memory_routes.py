from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.main import app


def test_project_memory_route_returns_current_document(tmp_path, monkeypatch):
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(tmp_path / "install-root"))
    client = TestClient(app)

    response = client.get("/api/project-memory")

    assert response.status_code == 200
    payload = response.json()
    assert "goal" in payload
    assert "rules" in payload
    assert "nextSteps" in payload


def test_project_memory_seed_route_builds_memory_from_goal_and_prompt(tmp_path, monkeypatch):
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(tmp_path / "install-root"))
    client = TestClient(app)

    response = client.post(
        "/api/project-memory/seed",
        json={
            "goal": "Napraviti HTML igru",
            "taskPrompt": "Mora imati score. Prvo dovrši collision.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["goal"]["text"] == "Napraviti HTML igru"
    assert any("score" in item["text"].lower() for item in payload["rules"])


def test_project_memory_update_route_persists_manual_edit(tmp_path, monkeypatch):
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(tmp_path / "install-root"))
    client = TestClient(app)

    response = client.post(
        "/api/project-memory/save",
        json={
            "goal": {"text": "Sačuvani cilj", "locked": False},
            "rules": [],
            "decisions": [],
            "progress": [],
            "nextSteps": [],
        },
    )

    assert response.status_code == 200
    assert response.json()["summary"].startswith("Project Memory")
