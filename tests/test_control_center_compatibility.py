from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.main import app


def test_compatibility_check_route_passes_catalog_model_id():
    expected = {"status": "radi", "checkedAt": "2026-05-23T12:00:00Z", "summary": "staje"}
    from unittest.mock import patch

    with patch(
        "local_ai_control_center_installer.control_center_backend.routes.compatibility.run_compatibility_check",
        return_value=expected,
    ) as service:
        client = TestClient(app)
        response = client.post("/api/compatibility/check", json={"catalogModelId": "unsloth/demo/demo.gguf"})

    assert response.status_code == 200
    assert response.json() == expected
    service.assert_called_once_with(catalog_model_id="unsloth/demo/demo.gguf", model=None, overrides=None)


def test_compatibility_apply_route_returns_result_and_updated_payload():
    expected = {
        "result": {"status": "ok", "summary": "primenjeno"},
        "compatibility": {"status": "granicno", "fitLabel": "Granicno", "summary": "ponovo provereno"},
    }
    from unittest.mock import patch

    with patch(
        "local_ai_control_center_installer.control_center_backend.routes.compatibility.apply_compatibility_action",
        return_value=expected,
    ) as service:
        client = TestClient(app)
        response = client.post(
            "/api/compatibility/apply",
            json={
                "catalogModelId": "unsloth/demo/demo.gguf",
                "action": {"kind": "set-runtime-preference", "value": "turboquant"},
            },
        )

    assert response.status_code == 200
    assert response.json() == expected
    service.assert_called_once()
