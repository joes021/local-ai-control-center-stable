from pathlib import Path


def test_knowledge_sources_keep_collection_and_tags(tmp_path: Path, monkeypatch):
    from local_ai_control_center_installer.control_center_backend.services import knowledge_service

    install_root = tmp_path / "install-root"
    source_dir = tmp_path / "docs"
    source_dir.mkdir(parents=True)
    (source_dir / "guide.txt").write_text("GPU memory planning for local llama runtime.", encoding="utf-8")

    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    add_result = knowledge_service.add_knowledge_source(
        str(source_dir),
        collection="Manuals",
        tags=["gpu", "llama"],
    )
    assert add_result["status"] == "ok"
    assert add_result["source"]["collection"] == "Manuals"
    assert add_result["source"]["tags"] == ["gpu", "llama"]

    reindex_result = knowledge_service.reindex_knowledge_sources()
    assert reindex_result["status"] == "ok"

    summary = knowledge_service.load_knowledge_summary()
    assert "Manuals" in summary["collections"]
    assert "gpu" in summary["tags"]
    assert "llama" in summary["tags"]

    query_result = knowledge_service.run_knowledge_query("memory", collection="Manuals")
    assert query_result["status"] == "ok"
    assert query_result["results"]
    assert query_result["results"][0]["collection"] == "Manuals"
    assert "gpu" in query_result["results"][0]["tags"]
