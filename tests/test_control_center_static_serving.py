from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.main import app


def test_control_center_serves_frontend_shell():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "Local AI Control Center" in response.text
