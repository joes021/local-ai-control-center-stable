from local_ai_control_center_installer.control_center_backend.services import browser_sources


def test_fetch_hf_models_keeps_late_gguf_variants_in_large_repo(monkeypatch):
    repo_id = "opensota/Qwen3.6-35B-A3B-GGUF"
    gguf_files = [
        {"rfilename": f"Qwen3.6-35B-A3B-UD-Q3_K_{index}.gguf"}
        for index in range(1, 20)
    ] + [{"rfilename": "Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf"}]

    def fake_read_json(url: str):
        if url.startswith(browser_sources.HF_API + "?"):
            return [
                {
                    "id": repo_id,
                    "siblings": gguf_files,
                    "lastModified": "2026-05-24T00:00:00Z",
                    "downloads": 2216,
                    "likes": 77,
                    "tags": ["gguf", "qwen"],
                }
            ]
        if f"{browser_sources.HF_API}/{repo_id}/tree/main" in url:
            return [{"path": entry["rfilename"], "size": 1024} for entry in gguf_files]
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(browser_sources, "_read_json", fake_read_json)

    result = browser_sources._fetch_hf_models(
        {
            "search": "GGUF",
            "limit": "80",
            "sort": "lastModified",
            "direction": "-1",
            "full": "true",
            "config": "false",
        },
        source="huggingface",
    )

    returned_filenames = [item["filename"] for item in result.models]

    assert len(returned_filenames) == 20
    assert "Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf" in returned_filenames


def test_browser_source_catalog_uses_broader_default_repo_limits(monkeypatch):
    captured: list[tuple[dict[str, str], str]] = []

    def fake_fetch(query: dict[str, str], *, source: str):
        captured.append((query, source))
        return browser_sources.SourceFetchResult(models=[], errors=[], warnings=[])

    monkeypatch.setattr(browser_sources, "_fetch_hf_models", fake_fetch)

    browser_sources.fetch_huggingface_catalog()
    browser_sources.fetch_unsloth_catalog()

    assert captured[0][1] == "huggingface"
    assert captured[1][1] == "unsloth"
    assert int(captured[0][0]["limit"]) >= 80
    assert int(captured[1][0]["limit"]) >= 80
