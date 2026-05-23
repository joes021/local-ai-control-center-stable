from pathlib import Path


def test_load_catalog_payload_prefers_cache_and_summarizes_refresh_metadata(tmp_path: Path):
    from local_ai_control_center_installer.control_center_backend.services import browser_catalog_service

    install_root = tmp_path / "install-root"
    cache_path = install_root / "config" / "control-center" / "browser-catalog-cache.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        """
{
  "models": [
    {
      "id": "hf/Qwen3-0.6B-Q8_0.gguf",
      "source": "huggingface",
      "repoId": "Qwen/Qwen3-0.6B-GGUF",
      "filename": "Qwen3-0.6B-Q8_0.gguf",
      "fit": {"status": "nije provereno"}
    },
    {
      "id": "unsloth/Qwen3.6-27B-GGUF/Qwen3.6-27B-UD-IQ3_XXS.gguf",
      "source": "unsloth",
      "repoId": "unsloth/Qwen3.6-27B-GGUF",
      "filename": "Qwen3.6-27B-UD-IQ3_XXS.gguf",
      "fit": {"status": "radi"}
    }
  ],
  "refresh": {
    "lastRefresh": "2026-05-23T10:00:00Z",
    "sources": {
      "huggingface": {
        "lastRefresh": "2026-05-23T10:00:00Z",
        "count": 1,
        "errors": [],
        "warnings": ["repo card missing context window"]
      },
      "unsloth": {
        "lastRefresh": "2026-05-23T10:02:00Z",
        "count": 1,
        "errors": [],
        "warnings": []
      }
    }
  }
}
""".strip(),
        encoding="utf-8",
    )

    payload = browser_catalog_service.load_catalog_payload(cache_path=cache_path)

    assert len(payload["models"]) == 2
    assert payload["refresh"]["counts"]["all"] == 2
    assert payload["refresh"]["counts"]["huggingface"] == 1
    assert payload["refresh"]["counts"]["unsloth"] == 1
    assert payload["refresh"]["warnings"] == ["repo card missing context window"]


def test_refresh_catalog_filters_to_gguf_and_updates_cache(tmp_path: Path):
    from local_ai_control_center_installer.control_center_backend.services import browser_catalog_service

    install_root = tmp_path / "install-root"
    cache_path = install_root / "config" / "control-center" / "browser-catalog-cache.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    def fake_fetch(source: str) -> dict[str, object]:
        assert source == "huggingface"
        return {
            "models": [
                {
                    "id": "hf-gguf",
                    "source": "huggingface",
                    "repoId": "Qwen/Qwen3-0.6B-GGUF",
                    "filename": "Qwen3-0.6B-Q8_0.gguf",
                    "sourceUrl": "https://huggingface.co/Qwen/Qwen3-0.6B-GGUF",
                },
                {
                    "id": "hf-non-gguf",
                    "source": "huggingface",
                    "repoId": "Qwen/Qwen3-0.6B",
                    "filename": "model.safetensors",
                    "sourceUrl": "https://huggingface.co/Qwen/Qwen3-0.6B",
                },
            ],
            "errors": [],
            "warnings": ["partial page limit"],
        }

    payload = browser_catalog_service.refresh_catalog(
        source="huggingface",
        cache_path=cache_path,
        fetch_source_catalog=fake_fetch,
        now_iso="2026-05-23T11:00:00Z",
    )

    cache_text = cache_path.read_text(encoding="utf-8")
    assert [item["id"] for item in payload["models"]] == ["hf-gguf"]
    assert payload["refresh"]["counts"]["huggingface"] == 1
    assert "partial page limit" in payload["refresh"]["warnings"]
    assert "hf-gguf" in cache_text
    assert "hf-non-gguf" not in cache_text


def test_update_model_fit_status_persists_last_known_fit(tmp_path: Path):
    from local_ai_control_center_installer.control_center_backend.services import browser_catalog_service

    install_root = tmp_path / "install-root"
    cache_path = install_root / "config" / "control-center" / "browser-catalog-cache.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        """
{
  "models": [
    {
      "id": "hf/Qwen3-0.6B-Q8_0.gguf",
      "source": "huggingface",
      "repoId": "Qwen/Qwen3-0.6B-GGUF",
      "filename": "Qwen3-0.6B-Q8_0.gguf",
      "fit": {"status": "nije provereno"}
    }
  ],
  "refresh": {"lastRefresh": "", "sources": {}}
}
""".strip(),
        encoding="utf-8",
    )

    browser_catalog_service.update_model_fit_status(
        "hf/Qwen3-0.6B-Q8_0.gguf",
        {"status": "radi", "checkedAt": "2026-05-23T11:30:00Z", "summary": "staje u masinu"},
        cache_path=cache_path,
    )
    payload = browser_catalog_service.load_catalog_payload(cache_path=cache_path)

    assert payload["models"][0]["fit"]["status"] == "radi"
    assert payload["models"][0]["fit"]["checkedAt"] == "2026-05-23T11:30:00Z"
