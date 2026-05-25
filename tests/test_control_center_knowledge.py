import json
from pathlib import Path
from zipfile import ZipFile

from local_ai_control_center_installer.control_center_backend.config import get_config


def _write_runtime_endpoint_config(install_root: Path, *, port: int = 39281) -> None:
    config_root = install_root / "config"
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "runtime-endpoint.json").write_text(
        json.dumps({"port": port, "base_url": f"http://127.0.0.1:{port}"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_active_model_config(install_root: Path, *, filename: str = "gemma-4-E4B-it-Q4_K_M.gguf") -> None:
    config_root = install_root / "config"
    config_root.mkdir(parents=True, exist_ok=True)
    model_path = install_root / "models" / "recommended-6gb" / filename
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text("model", encoding="utf-8")
    (config_root / "active-model.json").write_text(
        json.dumps({"model_id": "recommended-6gb", "model_path": str(model_path)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_settings_config(install_root: Path) -> None:
    control_center_root = install_root / "config" / "control-center"
    control_center_root.mkdir(parents=True, exist_ok=True)
    (control_center_root / "settings.json").write_text(
        json.dumps(
            {
                "profile": "balanced",
                "context": 131072,
                "outputTokens": 4096,
                "thinkingMode": "mid",
                "buildSteps": 140,
                "planSteps": 100,
                "generalSteps": 110,
                "exploreSteps": 80,
                "accessMode": "local-only",
                "webSearchMode": "on-demand",
                "webSearchProvider": "searxng",
                "webSearchBaseUrl": "http://127.0.0.1:18080",
                "webSearchMaxResults": 3,
                "webSearchTimeoutSeconds": 9,
                "webSearchPromptPrefix": "/web",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_docx(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            f"""
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:body>
                <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
              </w:body>
            </w:document>
            """.strip(),
        )


def test_control_center_config_exposes_knowledge_state_paths(tmp_path: Path, monkeypatch):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    config = get_config()

    assert config.knowledge_sources_path == install_root / "config" / "control-center" / "knowledge-sources.json"
    assert config.knowledge_history_path == install_root / "config" / "control-center" / "knowledge-history.json"
    assert config.knowledge_index_path == install_root / "config" / "control-center" / "knowledge-index.sqlite3"


def test_reindex_knowledge_sources_indexes_plain_text_and_docx_and_query_returns_hits(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services.knowledge_service import (
        add_knowledge_source,
        load_knowledge_summary,
        reindex_knowledge_sources,
        run_knowledge_query,
    )

    install_root = tmp_path / "install-root"
    knowledge_root = tmp_path / "knowledge"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    knowledge_root.mkdir(parents=True, exist_ok=True)
    (knowledge_root / "notes.md").write_text(
        "KV cache compression smanjuje memorijski pritisak i cuva throughput.",
        encoding="utf-8",
    )
    _write_docx(knowledge_root / "turboquant.docx", "TurboQuant koristi CUDA i kompresiju KV cache-a.")

    add_result = add_knowledge_source(str(knowledge_root))
    assert add_result["status"] == "ok"

    reindex_result = reindex_knowledge_sources()
    assert reindex_result["status"] == "ok"
    assert reindex_result["documentCount"] == 2
    assert reindex_result["indexedDocumentCount"] == 2

    summary = load_knowledge_summary()
    assert summary["sourceCount"] == 1
    assert summary["documentCount"] == 2
    assert summary["indexedDocumentCount"] == 2
    assert summary["sources"][0]["path"] == str(knowledge_root)

    query_payload = run_knowledge_query("CUDA")
    assert query_payload["status"] == "ok"
    assert query_payload["resultCount"] == 1
    assert query_payload["results"][0]["name"] == "turboquant.docx"
    assert "TurboQuant koristi CUDA" in query_payload["results"][0]["snippet"]


def test_answer_with_knowledge_supports_documents_only_and_documents_plus_web(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services.knowledge_service import (
        add_knowledge_source,
        answer_with_knowledge,
        reindex_knowledge_sources,
    )

    install_root = tmp_path / "install-root"
    knowledge_root = tmp_path / "knowledge"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_runtime_endpoint_config(install_root)
    _write_active_model_config(install_root)
    _write_settings_config(install_root)

    (knowledge_root / "docs.txt").parent.mkdir(parents=True, exist_ok=True)
    (knowledge_root / "docs.txt").write_text(
        "SearxNG je metasearch engine koji okuplja rezultate iz vise izvora.",
        encoding="utf-8",
    )

    add_knowledge_source(str(knowledge_root))
    reindex_knowledge_sources()

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.knowledge_service.ensure_runtime_ready",
        lambda config=None: {"status": "ok", "summary": "runtime ready"},
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.knowledge_service.load_runtime_state",
        lambda config=None: {
            "base_url": "http://127.0.0.1:39281",
            "active_model": "gemma-4-E4B-it-Q4_K_M.gguf",
            "active_runtime": "turboquant",
        },
    )

    captured_bodies: list[dict[str, object]] = []

    class _FakeRuntimeResponse:
        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [{"message": {"content": "Odgovor lokalnog modela."}}],
                    "usage": {"prompt_tokens": 111, "completion_tokens": 22, "total_tokens": 133},
                }
            ).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_opener(request, timeout):
        captured_bodies.append(json.loads(request.data.decode("utf-8")))
        assert timeout == 180.0
        return _FakeRuntimeResponse()

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.knowledge_service.perform_search_query",
        lambda query, **kwargs: {
            "status": "ok",
            "provider": "searxng",
            "mode": "manual",
            "query": query,
            "resultCount": 1,
            "summary": "Pronadjen je 1 web rezultat.",
            "results": [
                {
                    "title": "Web rezultat",
                    "url": "https://example.invalid/web",
                    "snippet": "Web snippet",
                    "engine": "demo",
                }
            ],
            "history": [],
        },
    )

    docs_only = answer_with_knowledge(
        "Objasni sta je SearxNG.",
        mode="documents-only",
        opener=fake_opener,
    )
    assert docs_only["status"] == "ok"
    assert docs_only["answerRuntime"] == "turboquant"
    assert docs_only["documentResultCount"] == 1
    assert docs_only["webResultCount"] == 0
    assert "SearxNG je metasearch engine" in str(captured_bodies[0]["messages"][0]["content"])

    docs_and_web = answer_with_knowledge(
        "Objasni sta je SearxNG.",
        mode="documents+web",
        opener=fake_opener,
    )
    assert docs_and_web["status"] == "ok"
    assert docs_and_web["documentResultCount"] == 1
    assert docs_and_web["webResultCount"] == 1
    assert "Web rezultat" in str(captured_bodies[1]["messages"][0]["content"])


def test_extract_pdf_text_uses_pypdf_reader(tmp_path: Path, monkeypatch):
    from local_ai_control_center_installer.control_center_backend.services.knowledge_service import _extract_pdf_text

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%mock\n")

    class _FakePage:
        def extract_text(self):
            return "PDF tekst"

    class _FakeReader:
        def __init__(self, path):
            assert str(path) == str(pdf_path)
            self.pages = [_FakePage()]

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.knowledge_service.PdfReader",
        _FakeReader,
    )

    assert _extract_pdf_text(pdf_path) == "PDF tekst"
