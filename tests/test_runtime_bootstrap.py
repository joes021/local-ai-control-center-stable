import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from local_ai_control_center_installer.runtime_bootstrap import (
    apply_runtime_payload,
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
    assert updated.runtime_artifact_status == "ready"
    assert updated.starter_model_status == "ready"
    assert updated.active_model_config_status == "ready"
    assert Path(updated.active_model_config_path).exists()


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


def test_apply_runtime_payload_maps_invalid_requested_model_manifest_entry_to_runtime_manifest_failure(
    tmp_path: Path,
):
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(tmp_path / "install-root"),
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


def test_apply_runtime_payload_maps_wrong_type_requested_model_manifest_entry_to_runtime_manifest_failure(
    tmp_path: Path,
):
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(tmp_path / "install-root"),
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
                "install_subdir": None,
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


def test_apply_runtime_payload_maps_manifest_load_error_to_runtime_manifest_failure(
    tmp_path: Path,
):
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(tmp_path / "install-root"),
        starter_model="recommended-6gb",
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


def test_apply_runtime_payload_marks_runtime_artifact_failure_and_skips_later_steps(
    tmp_path: Path,
):
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(tmp_path / "install-root"),
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
    assert updated.last_successful_step == "starter-model"
    assert updated.failing_step == "active-model-config"
