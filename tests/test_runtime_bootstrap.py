import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from local_ai_control_center_installer.runtime_bootstrap import (
    _write_active_model_config,
    _write_model_locations_config,
    _write_runtime_endpoint_config,
    apply_runtime_payload,
    load_runtime_endpoint_config,
    load_runtime_manifest,
    resolve_requested_starter_model,
)
from local_ai_control_center_installer.session import InstallerSession


PINNED_OK_RUNTIME_SHA256 = (
    "2689367b205c16ce32ed4200942b8b8b1e262dfc70d9bc9fbc77c49699a4f1df"
)
PINNED_TAMPERED_RUNTIME_SHA256 = (
    "d121be3103007b41edf96f8262925f8c7d61894afe9a041843b631f69445bc57"
)


def _runtime_download_plan(
    *,
    model_id: str = "recommended-6gb",
    include_runtime: bool = True,
    include_model: bool = True,
) -> dict:
    items: list[dict[str, object]] = []
    if include_runtime:
        items.append(
            {
                "key": "runtime-artifact",
                "label": "llama.cpp runtime",
                "url": "https://example.invalid/runtime.zip",
                "destination_hint": "runtime/llama.cpp",
                "size_bytes": None,
            }
        )
    if include_model:
        items.append(
            {
                "key": f"starter-model:{model_id}",
                "label": f"starter model {model_id}",
                "url": "https://example.invalid/model.gguf",
                "destination_hint": f"models/{model_id}/{model_id}.gguf",
                "size_bytes": 123,
            }
        )

    total = len(items)
    return {
        "items": [
            {
                **item,
                "queue_index": index,
                "queue_total": total,
            }
            for index, item in enumerate(items, start=1)
        ]
    }


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
                    "required_file_sha256": {
                        "llama-server.exe": PINNED_OK_RUNTIME_SHA256
                    },
                    "install_subdir": "runtime/llama.cpp",
                },
                "starter_models": {
                    "recommended-6gb": {
                        "id": "recommended-6gb",
                        "url": "https://example.invalid/model.gguf",
                        "sha256": "def456",
                        "target_filename": "recommended-6gb.gguf",
                        "install_subdir": "models/recommended-6gb",
                        "size_bytes": 123,
                        "prompt_order": 1,
                        "prompt_label": "recommended-6gb",
                        "recommended_default": True
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
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
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


def test_built_wheel_contains_runtime_manifest_json(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[1]
    wheel_dir = tmp_path / "wheelhouse"
    env = os.environ.copy()
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "-w", str(wheel_dir)],
        check=True,
        cwd=repo_root,
        env=env,
    )

    wheel_path = next(wheel_dir.glob("*.whl"))
    with zipfile.ZipFile(wheel_path) as wheel_archive:
        assert (
            "local_ai_control_center_installer/manifests/windows-stable-runtime.json"
            in wheel_archive.namelist()
        )


def test_apply_runtime_payload_skips_when_bootstrap_failed(tmp_path: Path):
    session = InstallerSession(
        bootstrap_status="failed",
        install_root=str(tmp_path / "install-root"),
        starter_model="recommended-6gb",
        failing_step="dependency-bootstrap",
        last_successful_step="dependency-scan",
    )

    updated = apply_runtime_payload(session, temp_root=tmp_path / "temp-runs")

    assert updated.runtime_payload_status == "skipped"
    assert updated.runtime_artifact_status == "skipped"
    assert updated.starter_model_status == "skipped"
    assert updated.active_model_config_status == "skipped"
    assert updated.failing_step == "dependency-bootstrap"
    assert updated.last_successful_step == "dependency-scan"


def test_apply_runtime_payload_marks_ready_when_runtime_and_model_are_verified_in_place(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    model_root = install_root / "models" / "recommended-6gb"
    metadata_path = runtime_root / "runtime-artifact.json"
    runtime_root.mkdir(parents=True)
    model_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
    (model_root / "recommended-6gb.gguf").write_text("ok", encoding="utf-8")
    metadata_path.write_text(
        json.dumps(
            {
                "artifact_id": "windows-llama-cpp-runtime",
                "source_sha256": "abc123",
            }
        ),
        encoding="utf-8",
    )
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        starter_model="recommended-6gb",
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "def456",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
                "size_bytes": 123,
            }
        },
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        verify_model_file=lambda path, expected_sha256: True,
        port_is_free=lambda host, port: True,
    )

    assert updated.runtime_payload_status == "ready"
    assert updated.runtime_artifact_status == "ready"
    assert updated.starter_model_status == "ready"
    assert updated.active_model_config_status == "ready"
    assert updated.model_locations_config_status == "ready"
    assert updated.runtime_endpoint_config_status == "ready"
    assert updated.managed_runtime_port == 39281
    assert Path(updated.active_model_config_path).exists()
    assert Path(updated.model_locations_config_path).exists()
    assert Path(updated.runtime_endpoint_config_path).exists()

    model_locations_payload = json.loads(
        Path(updated.model_locations_config_path).read_text(encoding="utf-8")
    )
    runtime_endpoint_payload = json.loads(
        Path(updated.runtime_endpoint_config_path).read_text(encoding="utf-8")
    )

    assert model_locations_payload == {
        "default_model_root": str(model_root),
        "additional_read_only_model_paths": [],
    }
    assert runtime_endpoint_payload == {
        "base_url": "http://127.0.0.1:39281",
        "port": 39281,
        "installer_managed": True,
    }


def test_apply_runtime_payload_writes_model_locations_with_additional_paths(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    model_root = install_root / "models" / "recommended-6gb"
    runtime_root.mkdir(parents=True)
    model_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
    (runtime_root / "runtime-artifact.json").write_text(
        json.dumps(
            {
                "artifact_id": "windows-llama-cpp-runtime",
                "source_sha256": "abc123",
            }
        ),
        encoding="utf-8",
    )
    (model_root / "recommended-6gb.gguf").write_text("ok", encoding="utf-8")
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        starter_model="recommended-6gb",
        additional_model_paths=["D:\\models", "E:\\shared-models"],
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "def456",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
                "size_bytes": 123,
            }
        },
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        verify_model_file=lambda path, expected_sha256: True,
    )

    payload = json.loads(
        Path(updated.model_locations_config_path).read_text(encoding="utf-8")
    )
    assert payload == {
        "default_model_root": str(model_root),
        "additional_read_only_model_paths": ["D:\\models", "E:\\shared-models"],
    }


def test_runtime_config_writers_preserve_previous_good_file_when_atomic_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    original_replace = Path.replace

    def fail_atomic_replace(self: Path, target: Path):
        if target in protected_targets and self != target:
            raise OSError("simulated replace failure")
        return original_replace(self, target)

    protected_targets = {
        tmp_path / "active-model.json",
        tmp_path / "model-locations.json",
        tmp_path / "runtime-endpoint.json",
    }
    monkeypatch.setattr(Path, "replace", fail_atomic_replace)

    active_model_config_path = tmp_path / "active-model.json"
    active_model_config_path.write_text('{"sentinel":"active"}', encoding="utf-8")
    with pytest.raises(OSError, match="simulated replace failure"):
        _write_active_model_config(
            active_model_config_path,
            model_id="recommended-6gb",
            model_path=Path("C:\\models\\recommended-6gb.gguf"),
        )
    assert (
        active_model_config_path.read_text(encoding="utf-8")
        == '{"sentinel":"active"}'
    )

    model_locations_config_path = tmp_path / "model-locations.json"
    model_locations_config_path.write_text('{"sentinel":"locations"}', encoding="utf-8")
    with pytest.raises(OSError, match="simulated replace failure"):
        _write_model_locations_config(
            model_locations_config_path,
            default_model_root=Path("C:\\models"),
            additional_paths=["D:\\models"],
        )
    assert (
        model_locations_config_path.read_text(encoding="utf-8")
        == '{"sentinel":"locations"}'
    )

    runtime_endpoint_config_path = tmp_path / "runtime-endpoint.json"
    runtime_endpoint_config_path.write_text('{"sentinel":"endpoint"}', encoding="utf-8")
    with pytest.raises(OSError, match="simulated replace failure"):
        _write_runtime_endpoint_config(
            runtime_endpoint_config_path,
            port=39281,
        )
    assert (
        runtime_endpoint_config_path.read_text(encoding="utf-8")
        == '{"sentinel":"endpoint"}'
    )


def test_load_runtime_endpoint_config_reads_canonical_managed_endpoint(
    tmp_path: Path,
):
    runtime_endpoint_config_path = _write_runtime_endpoint_config(
        tmp_path / "runtime-endpoint.json",
        port=39281,
    )

    config = load_runtime_endpoint_config(runtime_endpoint_config_path)

    assert config.port == 39281
    assert config.base_url == "http://127.0.0.1:39281"
    assert config.installer_managed is True


def test_apply_runtime_payload_chooses_free_managed_runtime_port_when_default_is_busy(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    model_root = install_root / "models" / "recommended-6gb"
    runtime_root.mkdir(parents=True)
    model_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
    (runtime_root / "runtime-artifact.json").write_text(
        json.dumps(
            {
                "artifact_id": "windows-llama-cpp-runtime",
                "source_sha256": "abc123",
            }
        ),
        encoding="utf-8",
    )
    (model_root / "recommended-6gb.gguf").write_text("ok", encoding="utf-8")
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        starter_model="recommended-6gb",
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "def456",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
                "size_bytes": 123,
            }
        },
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        verify_model_file=lambda path, expected_sha256: True,
        port_is_free=lambda host, port: port != 39281,
        choose_free_port=lambda host="127.0.0.1": 40123,
    )

    assert updated.runtime_payload_status == "ready"
    assert updated.managed_runtime_port == 40123
    runtime_endpoint_payload = json.loads(
        Path(updated.runtime_endpoint_config_path).read_text(encoding="utf-8")
    )
    assert runtime_endpoint_payload == {
        "base_url": "http://127.0.0.1:40123",
        "port": 40123,
        "installer_managed": True,
    }


def test_apply_runtime_payload_preserves_existing_managed_runtime_port_on_upgrade(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    model_root = install_root / "models" / "recommended-6gb"
    runtime_root.mkdir(parents=True)
    model_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
    (runtime_root / "runtime-artifact.json").write_text(
        json.dumps(
            {
                "artifact_id": "windows-llama-cpp-runtime",
                "source_sha256": "abc123",
            }
        ),
        encoding="utf-8",
    )
    (model_root / "recommended-6gb.gguf").write_text("ok", encoding="utf-8")
    existing_endpoint_path = _write_runtime_endpoint_config(
        install_root / "config" / "runtime-endpoint.json",
        port=41234,
    )
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        install_mode="upgrade",
        starter_model="recommended-6gb",
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "def456",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
                "size_bytes": 123,
            }
        },
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        verify_model_file=lambda path, expected_sha256: True,
        port_is_free=lambda host, port: False,
        choose_free_port=lambda host="127.0.0.1": 49999,
    )

    assert updated.runtime_payload_status == "ready"
    assert updated.managed_runtime_port == 41234
    runtime_endpoint_payload = json.loads(existing_endpoint_path.read_text(encoding="utf-8"))
    assert runtime_endpoint_payload == {
        "base_url": "http://127.0.0.1:41234",
        "port": 41234,
        "installer_managed": True,
    }


def test_apply_runtime_payload_preserves_existing_active_model_on_upgrade(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    model_root = install_root / "models" / "recommended-6gb"
    runtime_root.mkdir(parents=True)
    model_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
    (runtime_root / "runtime-artifact.json").write_text(
        json.dumps(
            {
                "artifact_id": "windows-llama-cpp-runtime",
                "source_sha256": "abc123",
            }
        ),
        encoding="utf-8",
    )
    (model_root / "recommended-6gb.gguf").write_text("ok", encoding="utf-8")
    existing_active_model_path = _write_active_model_config(
        install_root / "config" / "active-model.json",
        model_id="local-custom-model",
        model_path=Path("D:\\Models\\custom-qwen.gguf"),
    )
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        install_mode="upgrade",
        starter_model="recommended-6gb",
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "def456",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
                "size_bytes": 123,
            }
        },
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        verify_model_file=lambda path, expected_sha256: True,
        port_is_free=lambda host, port: True,
    )

    assert updated.runtime_payload_status == "ready"
    active_model_payload = json.loads(
        existing_active_model_path.read_text(encoding="utf-8")
    )
    assert active_model_payload == {
        "model_id": "local-custom-model",
        "model_path": "D:\\Models\\custom-qwen.gguf",
    }


def test_apply_runtime_payload_reassigns_stale_managed_runtime_port_on_fresh_reinstall(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    model_root = install_root / "models" / "recommended-6gb"
    runtime_root.mkdir(parents=True)
    model_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
    (runtime_root / "runtime-artifact.json").write_text(
        json.dumps(
            {
                "artifact_id": "windows-llama-cpp-runtime",
                "source_sha256": "abc123",
            }
        ),
        encoding="utf-8",
    )
    (model_root / "recommended-6gb.gguf").write_text("ok", encoding="utf-8")
    runtime_endpoint_path = _write_runtime_endpoint_config(
        install_root / "config" / "runtime-endpoint.json",
        port=39281,
    )
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        install_mode="fresh",
        starter_model="recommended-6gb",
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "def456",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
                "size_bytes": 123,
            }
        },
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        verify_model_file=lambda path, expected_sha256: True,
        port_is_free=lambda host, port: port != 39281,
        choose_free_port=lambda host="127.0.0.1": 40123,
    )

    assert updated.runtime_payload_status == "ready"
    assert updated.managed_runtime_port == 40123
    runtime_endpoint_payload = json.loads(
        runtime_endpoint_path.read_text(encoding="utf-8")
    )
    assert runtime_endpoint_payload == {
        "base_url": "http://127.0.0.1:40123",
        "port": 40123,
        "installer_managed": True,
    }


def test_apply_runtime_payload_clears_stale_error_message_when_runtime_phase_succeeds(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    model_root = install_root / "models" / "recommended-6gb"
    runtime_root.mkdir(parents=True)
    model_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
    (runtime_root / "runtime-artifact.json").write_text(
        json.dumps(
            {
                "artifact_id": "windows-llama-cpp-runtime",
                "source_sha256": "abc123",
            }
        ),
        encoding="utf-8",
    )
    (model_root / "recommended-6gb.gguf").write_text("ok", encoding="utf-8")
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        starter_model="recommended-6gb",
        error_message="stale failure",
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "def456",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
                "size_bytes": 123,
            }
        },
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        verify_model_file=lambda path, expected_sha256: True,
    )

    assert updated.runtime_payload_status == "ready"
    assert updated.error_message is None


def test_apply_runtime_payload_normalizes_and_deduplicates_additional_model_paths(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    model_root = install_root / "models" / "recommended-6gb"
    runtime_root.mkdir(parents=True)
    model_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
    (runtime_root / "runtime-artifact.json").write_text(
        json.dumps(
            {
                "artifact_id": "windows-llama-cpp-runtime",
                "source_sha256": "abc123",
            }
        ),
        encoding="utf-8",
    )
    (model_root / "recommended-6gb.gguf").write_text("ok", encoding="utf-8")
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        starter_model="recommended-6gb",
        additional_model_paths=[
            " D:\\models\\ ",
            "d:\\models",
            "E:\\shared-models\\",
            "",
            "   ",
        ],
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "def456",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
                "size_bytes": 123,
            }
        },
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        verify_model_file=lambda path, expected_sha256: True,
    )

    payload = json.loads(
        Path(updated.model_locations_config_path).read_text(encoding="utf-8")
    )
    assert payload["additional_read_only_model_paths"] == [
        str(Path("D:\\models")),
        str(Path("E:\\shared-models")),
    ]


@pytest.mark.parametrize("managed_runtime_port", [0, 70000, "39281", True])
def test_apply_runtime_payload_fails_when_managed_runtime_port_is_invalid(
    tmp_path: Path,
    managed_runtime_port,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    model_root = install_root / "models" / "recommended-6gb"
    runtime_root.mkdir(parents=True)
    model_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
    (runtime_root / "runtime-artifact.json").write_text(
        json.dumps(
            {
                "artifact_id": "windows-llama-cpp-runtime",
                "source_sha256": "abc123",
            }
        ),
        encoding="utf-8",
    )
    (model_root / "recommended-6gb.gguf").write_text("ok", encoding="utf-8")
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        starter_model="recommended-6gb",
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "def456",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
                "size_bytes": 123,
            }
        },
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        verify_model_file=lambda path, expected_sha256: True,
        managed_runtime_port=managed_runtime_port,
    )

    assert updated.runtime_payload_status == "failed"
    assert updated.runtime_endpoint_config_status == "failed"
    assert updated.failing_step == "runtime-endpoint-config"
    assert "managed runtime port" in (updated.error_message or "").lower()


def test_apply_runtime_payload_invalid_managed_port_clears_stale_ready_runtime_statuses(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        starter_model="recommended-6gb",
        runtime_payload_status="ready",
        runtime_artifact_status="ready",
        starter_model_status="ready",
        active_model_config_status="ready",
        model_locations_config_status="ready",
        runtime_endpoint_config_status="ready",
        managed_runtime_port=39281,
        last_successful_step="runtime-endpoint-config",
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "def456",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
                "size_bytes": 123,
            }
        },
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        managed_runtime_port=0,
    )

    assert updated.runtime_payload_status == "failed"
    assert updated.runtime_artifact_status == "skipped"
    assert updated.starter_model_status == "skipped"
    assert updated.active_model_config_status == "skipped"
    assert updated.model_locations_config_status == "skipped"
    assert updated.runtime_endpoint_config_status == "failed"
    assert updated.managed_runtime_port is None
    assert updated.last_successful_step is None
    assert updated.failing_step == "runtime-endpoint-config"


@pytest.mark.parametrize(
    ("starter_model_id", "target_filename", "install_subdir"),
    [
        (
            "recommended-12gb",
            "recommended-12gb.gguf",
            "models/recommended-12gb",
        ),
        (
            "recommended-24gb",
            "recommended-24gb.gguf",
            "models/recommended-24gb",
        ),
    ],
)
def test_apply_runtime_payload_supports_shared_manifest_starter_model_tiers(
    tmp_path: Path,
    starter_model_id: str,
    target_filename: str,
    install_subdir: str,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    model_root = install_root / install_subdir
    metadata_path = runtime_root / "runtime-artifact.json"
    runtime_root.mkdir(parents=True)
    model_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
    (model_root / target_filename).write_text("ok", encoding="utf-8")
    metadata_path.write_text(
        json.dumps(
            {
                "artifact_id": "windows-llama-cpp-runtime",
                "source_sha256": "abc123",
            }
        ),
        encoding="utf-8",
    )
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        starter_model=starter_model_id,
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            starter_model_id: {
                "id": starter_model_id,
                "url": f"https://example.invalid/{target_filename}",
                "sha256": "def456",
                "target_filename": target_filename,
                "install_subdir": install_subdir,
                "size_bytes": 123,
                "prompt_order": 2,
                "prompt_label": starter_model_id,
                "recommended_default": False,
            }
        },
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        verify_model_file=lambda path, expected_sha256: True,
    )

    assert updated.runtime_payload_status == "ready"
    assert updated.starter_model_status == "ready"
    assert Path(updated.starter_model_path).name == target_filename


def test_apply_runtime_payload_downloads_extracts_and_promotes_runtime_payload_when_missing(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    temp_root = tmp_path / "temp-runs"
    verify_archive_calls: list[tuple[Path, str]] = []
    verify_model_calls: list[tuple[Path, str]] = []
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root / ".." / install_root.name),
        starter_model="recommended-6gb",
        download_plan=_runtime_download_plan(),
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "runtime-sha",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "model-sha",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
                "size_bytes": 123,
            }
        },
    }

    def fake_download_runtime_archive(url: str, destination: Path) -> Path:
        destination.write_bytes(b"runtime-archive")
        return destination

    def fake_extract_archive(
        archive_path: Path,
        destination_root: Path,
        *,
        archive_type: str,
    ) -> Path:
        destination_root.mkdir(parents=True, exist_ok=True)
        (destination_root / "llama-server.exe").write_text("ok", encoding="utf-8")
        return destination_root

    def fake_download_model_file(url: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("model", encoding="utf-8")
        return destination

    def fake_verify_archive_sha256(path: Path, expected: str) -> bool:
        verify_archive_calls.append((path, expected))
        return True

    def fake_verify_model_file(path: Path, expected: str) -> bool:
        verify_model_calls.append((path, expected))
        return True

    updated = apply_runtime_payload(
        session,
        temp_root=temp_root,
        load_manifest=lambda: manifest,
        download_runtime_archive=fake_download_runtime_archive,
        download_model_file=fake_download_model_file,
        extract_archive=fake_extract_archive,
        verify_archive_sha256=fake_verify_archive_sha256,
        verify_model_file=fake_verify_model_file,
    )

    assert updated.runtime_payload_status == "ready"
    assert updated.runtime_artifact_status == "ready"
    assert updated.starter_model_status == "ready"
    assert updated.active_model_config_status == "ready"
    assert updated.install_root == str(install_root.resolve())
    assert Path(updated.runtime_artifact_path, "llama-server.exe").exists()
    assert Path(updated.runtime_metadata_path).exists()
    assert Path(updated.starter_model_path).exists()
    assert Path(updated.active_model_config_path).exists()
    assert Path(install_root, "config", "active-model.json").exists()
    assert len(verify_archive_calls) == 1
    assert verify_archive_calls[0][0].parent.name == "downloads"
    assert verify_archive_calls[0][0].name == "runtime-artifact.archive"
    assert verify_archive_calls[0][0].is_relative_to(temp_root)
    assert verify_archive_calls[0][1] == "runtime-sha"
    assert len(verify_model_calls) == 1
    assert verify_model_calls[0][0].name == "recommended-6gb.gguf"
    assert verify_model_calls[0][0].is_relative_to(temp_root)
    assert verify_model_calls[0][1] == "model-sha"


def test_apply_runtime_payload_redownloads_when_installed_required_runtime_file_was_tampered(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    model_root = install_root / "models" / "recommended-6gb"
    runtime_root.mkdir(parents=True)
    model_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("tampered", encoding="utf-8")
    (runtime_root / "runtime-artifact.json").write_text(
        json.dumps(
            {
                "artifact_id": "windows-llama-cpp-runtime",
                "source_sha256": "abc123",
                "required_file_sha256": {
                    "llama-server.exe": PINNED_TAMPERED_RUNTIME_SHA256
                },
            }
        ),
        encoding="utf-8",
    )
    (model_root / "recommended-6gb.gguf").write_text("ok", encoding="utf-8")
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        starter_model="recommended-6gb",
        download_plan=_runtime_download_plan(include_runtime=True, include_model=False),
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "def456",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
                "size_bytes": 123,
            }
        },
    }
    download_calls: list[tuple[str, Path]] = []

    def fake_download_runtime_archive(url: str, destination: Path) -> Path:
        download_calls.append((url, destination))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"runtime-archive")
        return destination

    def fake_extract_archive(
        archive_path: Path,
        destination_root: Path,
        *,
        archive_type: str,
    ) -> Path:
        destination_root.mkdir(parents=True, exist_ok=True)
        (destination_root / "llama-server.exe").write_text("ok", encoding="utf-8")
        return destination_root

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        download_runtime_archive=fake_download_runtime_archive,
        extract_archive=fake_extract_archive,
        verify_archive_sha256=lambda path, expected_sha256: True,
        verify_model_file=lambda path, expected_sha256: True,
    )

    assert updated.runtime_payload_status == "ready"
    assert updated.runtime_artifact_status == "ready"
    assert len(download_calls) == 1
    assert download_calls[0][0] == "https://example.invalid/runtime.zip"
    assert (runtime_root / "llama-server.exe").read_text(encoding="utf-8") == "ok"


def test_apply_runtime_payload_uses_session_download_plan_for_default_queue_items(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        starter_model="recommended-6gb",
        download_plan={
            **_runtime_download_plan()
        },
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "runtime-sha",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "model-sha",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
                "size_bytes": 123,
            }
        },
    }
    planned_items: list[object] = []

    def fake_shared_download(url: str, destination: Path, **kwargs) -> Path:
        planned_items.append(kwargs["plan_item"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"archive")
        return destination

    def fake_extract_archive(
        archive_path: Path,
        destination_root: Path,
        *,
        archive_type: str,
    ) -> Path:
        destination_root.mkdir(parents=True, exist_ok=True)
        (destination_root / "llama-server.exe").write_text("ok", encoding="utf-8")
        return destination_root

    monkeypatch.setattr(
        "local_ai_control_center_installer.runtime_bootstrap._download_file",
        fake_shared_download,
    )

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        extract_archive=fake_extract_archive,
        verify_archive_sha256=lambda path, expected_sha256: True,
        verify_model_file=lambda path, expected_sha256: True,
    )

    assert updated.runtime_payload_status == "ready"
    assert [item.label for item in planned_items] == [
        "llama.cpp runtime",
        "starter model recommended-6gb",
    ]


def test_apply_runtime_payload_fails_when_requested_model_manifest_entry_is_missing(
    tmp_path: Path,
):
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(tmp_path / "install-root"),
        starter_model="recommended-24gb",
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {},
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
    )

    assert updated.runtime_payload_status == "failed"
    assert updated.runtime_artifact_status == "skipped"
    assert updated.starter_model_status == "failed"
    assert updated.active_model_config_status == "skipped"
    assert updated.failing_step == "runtime-manifest"
    assert "missing starter model entry" in (updated.error_message or "").lower()


def test_apply_runtime_payload_maps_invalid_requested_model_manifest_entry_to_runtime_manifest_failure(
    tmp_path: Path,
):
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(tmp_path / "install-root"),
        starter_model="recommended-6gb",
        download_plan=_runtime_download_plan(include_runtime=True, include_model=False),
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "def456",
                "target_filename": "recommended-6gb.gguf",
                "size_bytes": 123,
            }
        },
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
    )

    assert updated.runtime_payload_status == "failed"
    assert updated.runtime_artifact_status == "skipped"
    assert updated.starter_model_status == "failed"
    assert updated.active_model_config_status == "skipped"
    assert updated.failing_step == "runtime-manifest"
    assert "missing required field" in (updated.error_message or "").lower()


def test_apply_runtime_payload_maps_wrong_type_requested_model_manifest_entry_to_runtime_manifest_failure(
    tmp_path: Path,
):
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(tmp_path / "install-root"),
        starter_model="recommended-6gb",
        download_plan=_runtime_download_plan(include_runtime=True, include_model=False),
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "def456",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": None,
                "size_bytes": 123,
            }
        },
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
    )

    assert updated.runtime_payload_status == "failed"
    assert updated.runtime_artifact_status == "skipped"
    assert updated.starter_model_status == "failed"
    assert updated.active_model_config_status == "skipped"
    assert updated.failing_step == "runtime-manifest"
    assert "field must be a non-empty string" in (updated.error_message or "").lower()


def test_apply_runtime_payload_maps_manifest_load_error_to_runtime_manifest_failure(
    tmp_path: Path,
):
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(tmp_path / "install-root"),
        starter_model="recommended-6gb",
        download_plan=_runtime_download_plan(include_runtime=True, include_model=False),
    )

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: (_ for _ in ()).throw(ValueError("bad manifest")),
    )

    assert updated.runtime_payload_status == "failed"
    assert updated.runtime_artifact_status == "failed"
    assert updated.starter_model_status == "failed"
    assert updated.active_model_config_status == "skipped"
    assert updated.failing_step == "runtime-manifest"
    assert updated.error_message == "bad manifest"


def test_apply_runtime_payload_marks_runtime_artifact_failure_and_skips_later_steps(
    tmp_path: Path,
):
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(tmp_path / "install-root"),
        starter_model="recommended-6gb",
        download_plan=_runtime_download_plan(include_runtime=True, include_model=False),
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "def456",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
                "size_bytes": 123,
            }
        },
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        download_runtime_archive=lambda *args, **kwargs: (_ for _ in ()).throw(
            OSError("download failed")
        ),
    )

    assert updated.runtime_payload_status == "failed"
    assert updated.runtime_artifact_status == "failed"
    assert updated.starter_model_status == "skipped"
    assert updated.active_model_config_status == "skipped"
    assert updated.failing_step == "runtime-artifact"
    assert updated.error_message == "download failed"


def test_apply_runtime_payload_maps_corrupt_runtime_metadata_to_runtime_artifact_failure(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
    (runtime_root / "runtime-artifact.json").write_text("{not-json", encoding="utf-8")
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        starter_model="recommended-6gb",
        download_plan=_runtime_download_plan(include_runtime=True, include_model=False),
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "def456",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
                "size_bytes": 123,
            }
        },
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        download_runtime_archive=lambda *args, **kwargs: (_ for _ in ()).throw(
            OSError("download failed")
        ),
    )

    assert updated.runtime_payload_status == "failed"
    assert updated.runtime_artifact_status == "failed"
    assert updated.starter_model_status == "skipped"
    assert updated.active_model_config_status == "skipped"
    assert updated.failing_step == "runtime-artifact"
    assert updated.error_message == "download failed"


def test_apply_runtime_payload_maps_undecodable_runtime_metadata_to_runtime_artifact_failure(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
    (runtime_root / "runtime-artifact.json").write_bytes(b"\xff\xfe\x00\x80")
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        starter_model="recommended-6gb",
        download_plan=_runtime_download_plan(include_runtime=True, include_model=False),
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "def456",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
                "size_bytes": 123,
            }
        },
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        download_runtime_archive=lambda *args, **kwargs: (_ for _ in ()).throw(
            OSError("download failed")
        ),
    )

    assert updated.runtime_payload_status == "failed"
    assert updated.runtime_artifact_status == "failed"
    assert updated.starter_model_status == "skipped"
    assert updated.active_model_config_status == "skipped"
    assert updated.failing_step == "runtime-artifact"
    assert updated.error_message == "download failed"


def test_apply_runtime_payload_marks_starter_model_failure_after_runtime_is_ready(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
    (runtime_root / "runtime-artifact.json").write_text(
        json.dumps(
            {
                "artifact_id": "windows-llama-cpp-runtime",
                "source_sha256": "abc123",
            }
        ),
        encoding="utf-8",
    )
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        starter_model="recommended-6gb",
        download_plan=_runtime_download_plan(include_runtime=False, include_model=True),
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "def456",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
                "size_bytes": 123,
            }
        },
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        verify_model_file=lambda path, expected_sha256: False,
        download_model_file=lambda *args, **kwargs: (_ for _ in ()).throw(
            OSError("model failed")
        ),
    )

    assert updated.runtime_payload_status == "failed"
    assert updated.runtime_artifact_status == "ready"
    assert updated.starter_model_status == "failed"
    assert updated.active_model_config_status == "skipped"
    assert updated.last_successful_step == "runtime-artifact"
    assert updated.failing_step == "starter-model"
    assert updated.error_message == "model failed"


def test_apply_runtime_payload_retries_starter_model_download_once_after_checksum_mismatch(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
    (runtime_root / "runtime-artifact.json").write_text(
        json.dumps(
            {
                "artifact_id": "windows-llama-cpp-runtime",
                "source_sha256": "abc123",
            }
        ),
        encoding="utf-8",
    )
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        starter_model="recommended-6gb",
        download_plan=_runtime_download_plan(include_runtime=False, include_model=True),
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "def456",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
                "size_bytes": 123,
            }
        },
    }
    download_attempts: list[int] = []
    verify_attempts = {"count": 0}

    def fake_download_model_file(url: str, destination: Path, *, plan_item=None) -> Path:
        del url, plan_item
        download_attempts.append(len(download_attempts) + 1)
        payload = b"bad-model" if len(download_attempts) == 1 else b"good-model"
        destination.write_bytes(payload)
        return destination

    def fake_verify_model_file(path: Path, expected_sha256: str) -> bool:
        del expected_sha256
        verify_attempts["count"] += 1
        return path.read_bytes() == b"good-model"

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        download_model_file=fake_download_model_file,
        verify_model_file=fake_verify_model_file,
    )

    assert updated.runtime_payload_status == "ready"
    assert updated.starter_model_status == "ready"
    assert download_attempts == [1, 2]
    assert verify_attempts["count"] == 2
    assert Path(updated.starter_model_path).read_bytes() == b"good-model"


def test_apply_runtime_payload_reports_actual_starter_model_checksum_after_retry_exhaustion(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
    (runtime_root / "runtime-artifact.json").write_text(
        json.dumps(
            {
                "artifact_id": "windows-llama-cpp-runtime",
                "source_sha256": "abc123",
            }
        ),
        encoding="utf-8",
    )
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        starter_model="recommended-6gb",
        download_plan=_runtime_download_plan(include_runtime=False, include_model=True),
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "expected-sha256",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
                "size_bytes": 123,
            }
        },
    }
    download_attempts: list[int] = []

    def fake_download_model_file(url: str, destination: Path, *, plan_item=None) -> Path:
        del url, plan_item
        download_attempts.append(len(download_attempts) + 1)
        destination.write_bytes(b"still-bad-model")
        return destination

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        download_model_file=fake_download_model_file,
        verify_model_file=lambda path, expected_sha256: False,
    )

    assert updated.runtime_payload_status == "failed"
    assert updated.starter_model_status == "failed"
    assert updated.failing_step == "starter-model"
    assert download_attempts == [1, 2]
    assert "Starter model checksum verification failed after 2 attempts." in (
        updated.error_message or ""
    )
    assert "Expected expected-sha256" in (updated.error_message or "")


def test_apply_runtime_payload_marks_active_model_config_failure_after_model_is_ready(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    model_root = install_root / "models" / "recommended-6gb"
    runtime_root.mkdir(parents=True)
    model_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
    (runtime_root / "runtime-artifact.json").write_text(
        json.dumps(
            {
                "artifact_id": "windows-llama-cpp-runtime",
                "source_sha256": "abc123",
            }
        ),
        encoding="utf-8",
    )
    (model_root / "recommended-6gb.gguf").write_text("ok", encoding="utf-8")
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        starter_model="recommended-6gb",
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "def456",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
                "size_bytes": 123,
            }
        },
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        verify_model_file=lambda path, expected_sha256: True,
        write_active_model_config=lambda *args, **kwargs: (_ for _ in ()).throw(
            OSError("config failed")
        ),
    )

    assert updated.runtime_payload_status == "failed"
    assert updated.runtime_artifact_status == "ready"
    assert updated.starter_model_status == "ready"
    assert updated.active_model_config_status == "failed"
    assert updated.model_locations_config_status == "skipped"
    assert updated.runtime_endpoint_config_status == "skipped"
    assert updated.last_successful_step == "starter-model"
    assert updated.failing_step == "active-model-config"
    assert updated.error_message == "config failed"


def test_apply_runtime_payload_marks_model_locations_config_failure_after_active_model_is_ready(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    model_root = install_root / "models" / "recommended-6gb"
    runtime_root.mkdir(parents=True)
    model_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
    (runtime_root / "runtime-artifact.json").write_text(
        json.dumps(
            {
                "artifact_id": "windows-llama-cpp-runtime",
                "source_sha256": "abc123",
            }
        ),
        encoding="utf-8",
    )
    (model_root / "recommended-6gb.gguf").write_text("ok", encoding="utf-8")
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        starter_model="recommended-6gb",
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "def456",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
                "size_bytes": 123,
            }
        },
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        verify_model_file=lambda path, expected_sha256: True,
        write_model_locations_config=lambda *args, **kwargs: (_ for _ in ()).throw(
            OSError("model locations failed")
        ),
    )

    assert updated.runtime_payload_status == "failed"
    assert updated.runtime_artifact_status == "ready"
    assert updated.starter_model_status == "ready"
    assert updated.active_model_config_status == "ready"
    assert updated.model_locations_config_status == "failed"
    assert updated.runtime_endpoint_config_status == "skipped"
    assert updated.last_successful_step == "active-model-config"
    assert updated.failing_step == "model-locations-config"
    assert updated.error_message == "model locations failed"


def test_apply_runtime_payload_marks_runtime_endpoint_config_failure_after_model_locations_are_ready(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    model_root = install_root / "models" / "recommended-6gb"
    runtime_root.mkdir(parents=True)
    model_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
    (runtime_root / "runtime-artifact.json").write_text(
        json.dumps(
            {
                "artifact_id": "windows-llama-cpp-runtime",
                "source_sha256": "abc123",
            }
        ),
        encoding="utf-8",
    )
    (model_root / "recommended-6gb.gguf").write_text("ok", encoding="utf-8")
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        starter_model="recommended-6gb",
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "def456",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
                "size_bytes": 123,
            }
        },
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        verify_model_file=lambda path, expected_sha256: True,
        write_runtime_endpoint_config=lambda *args, **kwargs: (_ for _ in ()).throw(
            OSError("runtime endpoint failed")
        ),
    )

    assert updated.runtime_payload_status == "failed"
    assert updated.runtime_artifact_status == "ready"
    assert updated.starter_model_status == "ready"
    assert updated.active_model_config_status == "ready"
    assert updated.model_locations_config_status == "ready"
    assert updated.runtime_endpoint_config_status == "failed"
    assert updated.last_successful_step == "model-locations-config"
    assert updated.failing_step == "runtime-endpoint-config"
    assert updated.error_message == "runtime endpoint failed"
