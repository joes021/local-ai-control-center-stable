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


def test_knowledge_routes_expose_summary_source_actions_query_and_answer(tmp_path: Path, monkeypatch):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_settings(install_root)

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.routes.knowledge.load_knowledge_summary",
        lambda: {
            "sourceCount": 1,
            "documentCount": 2,
            "indexedDocumentCount": 2,
            "sources": [{"id": "src-1", "path": "C:/docs"}],
            "history": [],
        },
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.routes.knowledge.add_knowledge_source",
        lambda path: {"status": "ok", "source": {"id": "src-1", "path": path}},
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.routes.knowledge.remove_knowledge_source",
        lambda source_id: {"status": "ok", "removedSourceId": source_id},
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.routes.knowledge.reindex_knowledge_sources",
        lambda: {"status": "ok", "documentCount": 2, "indexedDocumentCount": 2},
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.routes.knowledge.run_knowledge_query",
        lambda query, **kwargs: {
            "status": "ok",
            "query": query,
            "resultCount": 1,
            "results": [{"name": "doc.txt", "snippet": "snippet"}],
        },
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.routes.knowledge.answer_with_knowledge",
        lambda query, mode="documents-only", **kwargs: {
            "status": "ok",
            "query": query,
            "mode": mode,
            "answer": "Knowledge answer",
            "documentResultCount": 1,
            "webResultCount": 0,
        },
    )

    client = TestClient(app)

    summary = client.get("/api/knowledge")
    assert summary.status_code == 200
    assert summary.json()["sourceCount"] == 1

    add_response = client.post("/api/knowledge/sources/add", json={"path": "C:/docs"})
    assert add_response.status_code == 200
    assert add_response.json()["source"]["path"] == "C:/docs"

    remove_response = client.post("/api/knowledge/sources/remove", json={"sourceId": "src-1"})
    assert remove_response.status_code == 200
    assert remove_response.json()["removedSourceId"] == "src-1"

    reindex_response = client.post("/api/knowledge/reindex")
    assert reindex_response.status_code == 200
    assert reindex_response.json()["documentCount"] == 2

    query_response = client.post("/api/knowledge/query", json={"query": "kv cache"})
    assert query_response.status_code == 200
    assert query_response.json()["results"][0]["name"] == "doc.txt"

    answer_response = client.post(
        "/api/knowledge/answer",
        json={"query": "objasni", "mode": "documents-only"},
    )
    assert answer_response.status_code == 200
    assert answer_response.json()["answer"] == "Knowledge answer"
