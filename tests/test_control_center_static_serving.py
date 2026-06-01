import os

from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.main import app


def test_control_center_serves_frontend_shell():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "RuntimePilot" in response.text


def test_control_center_health_exposes_panel_identity(monkeypatch):
    monkeypatch.setenv("LACC_INSTALL_ROOT", "C:\\PanelRoot")

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app": "local-ai-control-center-stable",
        "installRoot": os.path.normpath("C:\\PanelRoot"),
    }
