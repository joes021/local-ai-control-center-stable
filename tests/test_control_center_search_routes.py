import json
from pathlib import Path

from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.main import app


def _write_settings(install_root: Path) -> None:
    settings_path = install_root / "config" / "control-center" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(
            {
                "webSearchMode": "on-demand",
                "webSearchProvider": "searxng",
                "webSearchBaseUrl": "http://127.0.0.1:18080",
                "webSearchMaxResults": 6,
                "webSearchTimeoutSeconds": 9,
                "webSearchPromptPrefix": "/web",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_search_routes_expose_settings_history_query_and_answer(tmp_path: Path, monkeypatch):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_settings(install_root)

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.routes.search.perform_search_query",
        lambda query, **kwargs: {
            "status": "ok",
            "provider": "searxng",
            "mode": "manual",
            "query": query,
            "resultCount": 1,
            "summary": "Pronadjen je 1 rezultat.",
            "results": [
                {
                    "title": "Result title",
                    "url": "https://example.invalid/result",
                    "snippet": "Result snippet",
                    "engine": "demo",
                }
            ],
            "history": [
                {
                    "query": query,
                    "mode": "manual",
                    "resultCount": 1,
                    "askedAt": "2026-05-25T00:00:00+00:00",
                }
            ],
        },
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.routes.search.answer_with_local_model",
        lambda query: {
            "status": "ok",
            "provider": "searxng",
            "mode": "manual",
            "query": query,
            "resultCount": 1,
            "summary": "Lokalni model je odgovorio.",
            "results": [
                {
                    "title": "Result title",
                    "url": "https://example.invalid/result",
                    "snippet": "Result snippet",
                    "engine": "demo",
                }
            ],
            "history": [],
            "answer": "Odgovor iz lokalnog modela.",
            "answerModel": "gemma.gguf",
            "answerRuntime": "llama.cpp",
            "usage": {
                "promptTokens": 12,
                "completionTokens": 34,
                "totalTokens": 46,
            },
        },
    )

    client = TestClient(app)

    summary = client.get("/api/search")
    assert summary.status_code == 200
    assert summary.json()["settings"]["mode"] == "on-demand"
    assert summary.json()["settings"]["baseUrl"] == "http://127.0.0.1:18080"
    assert summary.json()["history"] == []

    query_response = client.post("/api/search/query", json={"query": "qwen3.6 browser"})
    assert query_response.status_code == 200
    assert query_response.json()["query"] == "qwen3.6 browser"
    assert query_response.json()["results"][0]["title"] == "Result title"

    answer_response = client.post("/api/search/answer", json={"query": "objasni kv cache"})
    assert answer_response.status_code == 200
    assert answer_response.json()["answer"] == "Odgovor iz lokalnog modela."
    assert answer_response.json()["answerRuntime"] == "llama.cpp"
