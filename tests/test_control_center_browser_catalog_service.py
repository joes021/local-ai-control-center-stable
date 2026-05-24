import json
from pathlib import Path


def _write_active_model_config(install_root: Path, *, model_id: str, model_path: Path) -> None:
    config_root = install_root / "config"
    config_root.mkdir(parents=True, exist_ok=True)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text("model", encoding="utf-8")
    (config_root / "active-model.json").write_text(
        json.dumps({"model_id": model_id, "model_path": str(model_path)}),
        encoding="utf-8",
    )


def _write_custom_registry(install_root: Path, models: list[dict[str, object]]) -> None:
    registry_path = install_root / "config" / "control-center" / "custom-models.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps({"models": models}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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


def test_load_catalog_payload_applies_browser_filters_and_search(tmp_path: Path):
    from local_ai_control_center_installer.control_center_backend.services import browser_catalog_service

    cache_path = tmp_path / "install-root" / "config" / "control-center" / "browser-catalog-cache.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        """
{
  "models": [
    {
      "id": "match-unsloth-iq2",
      "model": "Qwen3.6-35B-A3B",
      "family": "Qwen",
      "source": "unsloth",
      "repoId": "unsloth/Qwen3.6-35B-A3B-GGUF",
      "filename": "Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf",
      "quantization": "UD-IQ2_XXS",
      "sizeBytes": 10737418240,
      "updatedAt": "2026-05-23T10:00:00Z",
      "mtpStatus": "no-mtp",
      "summary": "Qwen3.6 non-MTP GGUF"
    },
    {
      "id": "match-mtp-iq2",
      "model": "Qwen3.6-35B-A3B",
      "family": "Qwen",
      "source": "unsloth",
      "repoId": "unsloth/Qwen3.6-35B-A3B-MTP-GGUF",
      "filename": "Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf",
      "quantization": "UD-IQ2_XXS",
      "sizeBytes": 10844792422,
      "updatedAt": "2026-05-22T10:00:00Z",
      "mtpStatus": "has-mtp",
      "summary": "Qwen3.6 MTP GGUF"
    },
    {
      "id": "other-quant",
      "model": "Qwen3.6-35B-A3B",
      "family": "Qwen",
      "source": "unsloth",
      "repoId": "unsloth/Qwen3.6-35B-A3B-GGUF",
      "filename": "Qwen3.6-35B-A3B-Q4_K_M.gguf",
      "quantization": "Q4_K_M",
      "sizeBytes": 21474836480,
      "updatedAt": "2026-05-21T10:00:00Z",
      "mtpStatus": "no-mtp",
      "summary": "Qwen3.6 Q4 variant"
    },
    {
      "id": "other-source",
      "model": "Llama-3.1-8B",
      "family": "Llama",
      "source": "huggingface",
      "repoId": "meta-llama/Llama-3.1-8B-GGUF",
      "filename": "Llama-3.1-8B-IQ2_XXS.gguf",
      "quantization": "IQ2_XXS",
      "sizeBytes": 3221225472,
      "updatedAt": "2026-05-23T09:00:00Z",
      "mtpStatus": "unknown",
      "summary": "Other source model"
    }
  ],
  "refresh": {
    "lastRefresh": "2026-05-23T10:00:00Z",
    "sources": {}
  }
}
""".strip(),
        encoding="utf-8",
    )

    payload = browser_catalog_service.load_catalog_payload(
        cache_path=cache_path,
        source="unsloth",
        search="qwen3.6-35b-a3b",
        family="Qwen",
        quant="IQ2_XXS",
        size="medium",
        mtp="has-mtp",
        date="30d",
        now_iso="2026-05-24T10:00:00Z",
    )

    assert [item["id"] for item in payload["models"]] == ["match-mtp-iq2"]
    assert payload["refresh"]["counts"]["all"] == 4
    assert payload["refresh"]["counts"]["unsloth"] == 3


def test_load_catalog_payload_sorts_catalog_rows_server_side(tmp_path: Path):
    from local_ai_control_center_installer.control_center_backend.services import browser_catalog_service

    cache_path = tmp_path / "install-root" / "config" / "control-center" / "browser-catalog-cache.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        """
{
  "models": [
    {
      "id": "q4",
      "model": "Model Q4",
      "family": "Qwen",
      "source": "unsloth",
      "repoId": "unsloth/model-q4",
      "filename": "model-q4.gguf",
      "quantization": "Q4_K_M",
      "sizeBytes": 17179869184,
      "updatedAt": "2026-05-21T10:00:00Z",
      "mtpStatus": "no-mtp"
    },
    {
      "id": "iq2",
      "model": "Model IQ2",
      "family": "Qwen",
      "source": "unsloth",
      "repoId": "unsloth/model-iq2",
      "filename": "model-iq2.gguf",
      "quantization": "UD-IQ2_XXS",
      "sizeBytes": 9663676416,
      "updatedAt": "2026-05-23T10:00:00Z",
      "mtpStatus": "no-mtp"
    },
    {
      "id": "bf16",
      "model": "Model BF16",
      "family": "Qwen",
      "source": "huggingface",
      "repoId": "hf/model-bf16",
      "filename": "model-bf16.gguf",
      "quantization": "BF16",
      "sizeBytes": 25769803776,
      "updatedAt": "2026-05-20T10:00:00Z",
      "mtpStatus": "unknown"
    }
  ],
  "refresh": {
    "lastRefresh": "2026-05-23T10:00:00Z",
    "sources": {}
  }
}
""".strip(),
        encoding="utf-8",
    )

    quant_sorted = browser_catalog_service.load_catalog_payload(cache_path=cache_path, sort="quant-asc")
    size_sorted = browser_catalog_service.load_catalog_payload(cache_path=cache_path, sort="size-desc")
    updated_sorted = browser_catalog_service.load_catalog_payload(cache_path=cache_path, sort="updated-desc")

    assert [item["id"] for item in quant_sorted["models"]] == ["iq2", "q4", "bf16"]
    assert [item["id"] for item in size_sorted["models"]] == ["bf16", "q4", "iq2"]
    assert [item["id"] for item in updated_sorted["models"]] == ["iq2", "q4", "bf16"]


def test_load_catalog_payload_marks_rows_already_added_to_local_catalog(tmp_path: Path):
    from local_ai_control_center_installer.control_center_backend.config import ControlCenterConfig
    from local_ai_control_center_installer.control_center_backend.services import browser_catalog_service
    from local_ai_control_center_installer.runtime_bootstrap import _write_runtime_endpoint_config

    install_root = tmp_path / "install-root"
    cache_path = install_root / "config" / "control-center" / "browser-catalog-cache.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        """
{
  "models": [
    {
      "id": "browser-qwen",
      "model": "Qwen 0.6B",
      "family": "Qwen",
      "source": "huggingface",
      "repoId": "Qwen/Qwen3-0.6B-GGUF",
      "filename": "Qwen3-0.6B-Q8_0.gguf",
      "quantization": "Q8_0",
      "sizeBytes": 2147483648,
      "updatedAt": "2026-05-23T10:00:00Z",
      "mtpStatus": "unknown"
    },
    {
      "id": "browser-other",
      "model": "Other",
      "family": "Other",
      "source": "huggingface",
      "repoId": "Other/Repo",
      "filename": "Other-Q4.gguf",
      "quantization": "Q4_K_M",
      "sizeBytes": 3221225472,
      "updatedAt": "2026-05-22T10:00:00Z",
      "mtpStatus": "unknown"
    }
  ],
  "refresh": {
    "lastRefresh": "2026-05-23T10:00:00Z",
    "sources": {}
  }
}
""".strip(),
        encoding="utf-8",
    )

    curated_model_path = install_root / "models" / "recommended-6gb" / "gemma-4-E4B-it-Q4_K_M.gguf"
    _write_active_model_config(
        install_root,
        model_id="recommended-6gb",
        model_path=curated_model_path,
    )
    _write_runtime_endpoint_config(install_root / "config" / "runtime-endpoint.json", port=39281)
    _write_custom_registry(
        install_root,
        [
            {
                "id": "huggingface-qwen-qwen3-0-6b-gguf-qwen3-0-6b-q8-0",
                "label": "Qwen 0.6B",
                "filename": "Qwen3-0.6B-Q8_0.gguf",
                "family": "Qwen",
                "source": "huggingface",
                "repo": "Qwen/Qwen3-0.6B-GGUF",
                "download_url": "https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/main/Qwen3-0.6B-Q8_0.gguf",
            }
        ],
    )

    config = ControlCenterConfig(
        ui_host="127.0.0.1",
        ui_port=3210,
        install_root=install_root,
        access_mode="local-only",
    )
    payload = browser_catalog_service.load_catalog_payload(cache_path=cache_path, config=config)

    matching = next(item for item in payload["models"] if item["id"] == "browser-qwen")
    other = next(item for item in payload["models"] if item["id"] == "browser-other")

    assert matching["addedToLocal"] is True
    assert matching["localModelId"] == "huggingface-qwen-qwen3-0-6b-gguf-qwen3-0-6b-q8-0"
    assert other["addedToLocal"] is False
    assert other["localModelId"] is None
