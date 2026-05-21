import json
from pathlib import Path

import pytest

from local_ai_control_center_installer.runtime_bootstrap import (
    load_runtime_manifest,
    resolve_requested_starter_model,
)


def test_load_runtime_manifest_reads_pinned_runtime_contract(tmp_path: Path):
    manifest_path = tmp_path / "windows-stable-runtime.json"
    manifest_path.write_text(
        json.dumps(
            {
                "runtime_artifact": {
                    "id": "windows-llama-cpp-runtime",
                    "url": "https://example.invalid/runtime.zip",
                    "sha256": "abc123",
                    "archive_type": "zip",
                    "required_files": ["llama-server.exe"],
                    "install_subdir": "runtime/llama.cpp",
                },
                "starter_models": {
                    "recommended-6gb": {
                        "id": "recommended-6gb",
                        "url": "https://example.invalid/model.gguf",
                        "sha256": "def456",
                        "target_filename": "recommended-6gb.gguf",
                        "install_subdir": "models/recommended-6gb",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    manifest = load_runtime_manifest(manifest_path)

    assert manifest["runtime_artifact"]["id"] == "windows-llama-cpp-runtime"
    assert (
        manifest["starter_models"]["recommended-6gb"]["target_filename"]
        == "recommended-6gb.gguf"
    )


def test_resolve_requested_starter_model_fails_for_missing_manifest_entry():
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {},
    }

    with pytest.raises(ValueError, match="starter model"):
        resolve_requested_starter_model(manifest, "recommended-24gb")


def test_load_runtime_manifest_uses_packaged_resource_by_default():
    manifest = load_runtime_manifest()

    assert "runtime_artifact" in manifest
    assert "starter_models" in manifest
    assert manifest["runtime_artifact"]["id"] == "windows-llama-cpp-runtime"
