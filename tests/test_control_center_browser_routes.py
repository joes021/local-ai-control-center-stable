from unittest.mock import patch

from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.main import app


def test_browser_catalog_route_returns_service_payload():
    expected = {"models": [], "refresh": {"counts": {"all": 0, "huggingface": 0, "unsloth": 0}}}
    with patch(
        "local_ai_control_center_installer.control_center_backend.routes.browser.load_catalog_payload",
        return_value=expected,
    ) as service:
        client = TestClient(app)
        response = client.get(
            "/api/browser/catalog",
            params={
                "source": "unsloth",
                "search": "qwen3",
                "family": "Qwen",
                "quant": "IQ2_XXS",
                "size": "medium",
                "mtp": "has-mtp",
                "date": "30d",
                "sort": "quant-asc",
                "limit": 25,
            },
        )

    assert response.status_code == 200
    assert response.json() == expected
    service.assert_called_once_with(
        source="unsloth",
        search="qwen3",
        family="Qwen",
        quant="IQ2_XXS",
        size="medium",
        mtp="has-mtp",
        date="30d",
        sort="quant-asc",
        limit=25,
    )


def test_browser_refresh_route_passes_source():
    expected = {"models": [{"id": "hf-1"}], "refresh": {"counts": {"all": 1, "huggingface": 1, "unsloth": 0}}}
    with patch(
        "local_ai_control_center_installer.control_center_backend.routes.browser.refresh_catalog",
        return_value=expected,
    ) as service:
        client = TestClient(app)
        response = client.post("/api/browser/catalog/refresh", json={"source": "huggingface"})

    assert response.status_code == 200
    assert response.json() == expected
    service.assert_called_once_with(source="huggingface")


def test_browser_add_route_uses_catalog_add_helper():
    expected = {
        "status": "ok",
        "summary": "HF model dodat u spisak: demo.gguf. Sledeći korak je Download.",
        "localModelId": "huggingface-demo",
    }
    with patch(
        "local_ai_control_center_installer.control_center_backend.routes.browser.add_catalog_model",
        return_value=expected,
    ) as service:
        client = TestClient(app)
        response = client.post(
            "/api/browser/catalog/add",
            json={
                "source": "huggingface",
                "repoId": "Qwen/Qwen3-0.6B-GGUF",
                "filename": "demo.gguf",
                "label": "Demo",
                "family": "Qwen",
            },
        )

    assert response.status_code == 200
    assert response.json() == expected
    service.assert_called_once_with(
        source="huggingface",
        repo_id="Qwen/Qwen3-0.6B-GGUF",
        filename="demo.gguf",
        label="Demo",
        family="Qwen",
    )


def test_browser_download_route_registers_model_then_starts_download():
    add_result = {
        "status": "ok",
        "summary": "Model dodat.",
        "localModelId": "unsloth-demo.gguf",
    }
    download_result = {
        "status": "ok",
        "action": "models-download",
        "summary": "Download pokrenut.",
        "details": {"returncode": 0, "stdout": "", "stderr": ""},
    }
    with (
        patch(
            "local_ai_control_center_installer.control_center_backend.routes.browser.add_catalog_model",
            return_value=add_result,
        ) as add_service,
        patch(
            "local_ai_control_center_installer.control_center_backend.routes.browser.download_model",
            return_value=download_result,
        ) as download_service,
    ):
        client = TestClient(app)
        response = client.post(
            "/api/browser/catalog/download",
            json={
                "source": "unsloth",
                "repoId": "unsloth/Qwen3.6-35B-A3B-GGUF",
                "filename": "Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf",
                "label": "Qwen3.6 35B",
                "family": "Qwen",
            },
        )

    assert response.status_code == 200
    assert response.json()["summary"] == "Download pokrenut."
    add_service.assert_called_once()
    download_service.assert_called_once_with("unsloth-demo.gguf")
