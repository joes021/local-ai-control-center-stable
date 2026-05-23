import json
from pathlib import Path

from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.main import app
from local_ai_control_center_installer.runtime_bootstrap import (
    _write_runtime_endpoint_config,
)


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


def test_models_route_merges_curated_and_custom_registry_rows_without_duplicate_ids(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    curated_model_path = (
        install_root / "models" / "recommended-6gb" / "gemma-4-E4B-it-Q4_K_M.gguf"
    )
    local_model_path = install_root / "models" / "local" / "custom-local.gguf"
    local_model_path.parent.mkdir(parents=True, exist_ok=True)
    local_model_path.write_text("local-model", encoding="utf-8")

    _write_active_model_config(
        install_root,
        model_id="recommended-6gb",
        model_path=curated_model_path,
    )
    _write_runtime_endpoint_config(
        install_root / "config" / "runtime-endpoint.json",
        port=39281,
    )
    _write_custom_registry(
        install_root,
        [
            {
                "id": "local-custom-local",
                "label": "Custom local",
                "filename": "custom-local.gguf",
                "family": "Custom",
                "source": "local",
                "absolute_path": str(local_model_path),
            },
            {
                "id": "huggingface-qwen-qwen3-0-6b-gguf-qwen3-0-6b-q8-0",
                "label": "Qwen 0.6B",
                "filename": "Qwen3-0.6B-Q8_0.gguf",
                "family": "Qwen",
                "source": "huggingface",
                "repo": "Qwen/Qwen3-0.6B-GGUF",
                "download_url": "https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/main/Qwen3-0.6B-Q8_0.gguf",
            },
            {
                "id": "unsloth-qwen3-6-27b-gguf-qwen3-6-27b-ud-iq3-xxs",
                "label": "Qwen3.6 27B",
                "filename": "Qwen3.6-27B-UD-IQ3_XXS.gguf",
                "family": "Unsloth",
                "source": "unsloth",
                "repo": "unsloth/Qwen3.6-27B-GGUF",
                "download_url": "https://huggingface.co/unsloth/Qwen3.6-27B-GGUF/resolve/main/Qwen3.6-27B-UD-IQ3_XXS.gguf",
            },
        ],
    )

    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    client = TestClient(app)
    response = client.get("/api/models")

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload["curated"]] == [
        "recommended-6gb",
        "recommended-12gb",
        "recommended-24gb",
    ]
    curated = next(item for item in payload["curated"] if item["id"] == "recommended-6gb")
    assert curated["active"] is True
    assert curated["installed"] is True
    assert curated["label"] == "gemma-4-E4B-it-Q4_K_M.gguf (recommended-6gb)"

    assert len(payload["local"]) == 1
    assert payload["local"][0]["installed"] is True
    assert payload["local"][0]["id"] == "local-custom-local"

    assert len(payload["huggingFace"]) == 1
    assert payload["huggingFace"][0]["installed"] is False
    assert payload["huggingFace"][0]["source"] == "huggingface"

    assert len(payload["unsloth"]) == 1
    assert payload["unsloth"][0]["mtpStatus"] == "no-mtp"

    all_ids = [
        item["id"]
        for group_name in ("curated", "local", "huggingFace", "unsloth")
        for item in payload[group_name]
    ]
    assert len(all_ids) == len(set(all_ids))


def test_activate_model_route_updates_active_model_and_managed_opencode_config(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    curated_model_path = (
        install_root / "models" / "recommended-6gb" / "gemma-4-E4B-it-Q4_K_M.gguf"
    )
    hf_model_path = (
        install_root
        / "models"
        / "huggingface"
        / "qwen-qwen3-0-6b-gguf"
        / "Qwen3-0.6B-Q8_0.gguf"
    )
    hf_model_path.parent.mkdir(parents=True, exist_ok=True)
    hf_model_path.write_text("hf-model", encoding="utf-8")
    _write_active_model_config(
        install_root,
        model_id="recommended-6gb",
        model_path=curated_model_path,
    )
    _write_runtime_endpoint_config(
        install_root / "config" / "runtime-endpoint.json",
        port=39281,
    )
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
                "absolute_path": str(hf_model_path),
                "download_url": "https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/main/Qwen3-0.6B-Q8_0.gguf",
            }
        ],
    )

    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.models_service.find_runtime_pid",
        lambda *args, **kwargs: None,
    )

    client = TestClient(app)
    response = client.post(
        "/api/models/activate",
        json={"modelId": "huggingface-qwen-qwen3-0-6b-gguf-qwen3-0-6b-q8-0"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "OpenCode config je osvezen" in payload["summary"]

    active_model_payload = json.loads(
        (install_root / "config" / "active-model.json").read_text(encoding="utf-8")
    )
    assert active_model_payload["model_id"] == "huggingface-qwen-qwen3-0-6b-gguf-qwen3-0-6b-q8-0"
    assert active_model_payload["model_path"] == str(hf_model_path)

    managed_config = json.loads(
        (install_root / "config" / "opencode" / "managed-config.json").read_text(
            encoding="utf-8"
        )
    )
    assert managed_config["model"] == "local-lacc/Qwen3-0.6B-Q8_0.gguf"
    assert managed_config["provider"]["local-lacc"]["options"]["baseURL"] == "http://127.0.0.1:39281/v1"
    assert managed_config["provider"]["local-lacc"]["models"] == {
        "Qwen3-0.6B-Q8_0.gguf": {"name": "Qwen3-0.6B-Q8_0.gguf"}
    }
