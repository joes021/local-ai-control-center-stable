import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from local_ai_control_center_installer.opencode_bootstrap import (
    apply_opencode_bootstrap,
    load_opencode_manifest,
)
from local_ai_control_center_installer.session import InstallerSession


def _sha256_for_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _build_opencode_manifest(
    *,
    artifact_id: str = "windows-opencode",
    artifact_sha256: str = "archive-sha",
    install_subdir: str = "tools/opencode",
    required_files: list[str] | None = None,
    required_file_sha256: dict[str, str] | None = None,
) -> dict:
    if required_files is None:
        required_files = ["opencode.exe"]
    if required_file_sha256 is None:
        required_file_sha256 = {"opencode.exe": _sha256_for_text("ok")}

    return {
        "opencode_artifact": {
            "id": artifact_id,
            "url": "https://example.invalid/opencode.zip",
            "sha256": artifact_sha256,
            "archive_type": "zip",
            "required_files": required_files,
            "required_file_sha256": required_file_sha256,
            "install_subdir": install_subdir,
            "launch": {
                "executable_relative_path": "opencode.exe",
                "verification_args": ["--pure", "run", "--format", "json", "--model"],
                "extra_env": {},
            },
        }
    }


def _write_active_model_config(path: Path, *, model_id: str = "recommended-6gb") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"model_id": model_id}, indent=2), encoding="utf-8")
    return path


def _opencode_download_plan() -> dict:
    return {
        "items": [
            {
                "key": "opencode-artifact",
                "label": "OpenCode",
                "url": "https://example.invalid/opencode.zip",
                "destination_hint": "tools/opencode",
                "size_bytes": None,
                "queue_index": 1,
                "queue_total": 1,
            }
        ]
    }


def test_load_opencode_manifest_reads_pinned_contract(tmp_path: Path):
    manifest_path = tmp_path / "windows-stable-opencode.json"
    manifest_path.write_text(
        json.dumps(
            {
                "opencode_artifact": {
                    "id": "windows-opencode",
                    "url": "https://github.com/anomalyco/opencode/releases/download/v1.15.7/opencode-windows-x64.zip",
                    "sha256": "8ac96b52692a3daeb84a20295cc7ed43aa3c698078e802926a47aef83748eab2",
                    "archive_type": "zip",
                    "required_files": ["opencode.exe"],
                    "required_file_sha256": {
                        "opencode.exe": "c18594c5368598f242387a2b6f505039a82b628c282101e99cb4452bd7622ed1"
                    },
                    "install_subdir": "tools/opencode",
                    "launch": {
                        "executable_relative_path": "opencode.exe",
                        "verification_args": [
                            "--pure",
                            "run",
                            "--format",
                            "json",
                            "--model",
                        ],
                        "extra_env": {},
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    manifest = load_opencode_manifest(manifest_path)

    assert manifest["opencode_artifact"] == {
        "id": "windows-opencode",
        "url": "https://github.com/anomalyco/opencode/releases/download/v1.15.7/opencode-windows-x64.zip",
        "sha256": "8ac96b52692a3daeb84a20295cc7ed43aa3c698078e802926a47aef83748eab2",
        "archive_type": "zip",
        "required_files": ["opencode.exe"],
        "required_file_sha256": {
            "opencode.exe": "c18594c5368598f242387a2b6f505039a82b628c282101e99cb4452bd7622ed1"
        },
        "install_subdir": "tools/opencode",
        "launch": {
            "executable_relative_path": "opencode.exe",
            "verification_args": [
                "--pure",
                "run",
                "--format",
                "json",
                "--model",
            ],
            "extra_env": {},
        },
    }


def test_load_opencode_manifest_uses_packaged_pinned_contract():
    manifest = load_opencode_manifest()

    assert manifest["opencode_artifact"] == {
        "id": "windows-opencode",
        "url": "https://github.com/anomalyco/opencode/releases/download/v1.15.7/opencode-windows-x64.zip",
        "sha256": "8ac96b52692a3daeb84a20295cc7ed43aa3c698078e802926a47aef83748eab2",
        "archive_type": "zip",
        "required_files": ["opencode.exe"],
        "required_file_sha256": {
            "opencode.exe": "c18594c5368598f242387a2b6f505039a82b628c282101e99cb4452bd7622ed1"
        },
        "install_subdir": "tools/opencode",
        "launch": {
            "executable_relative_path": "opencode.exe",
            "verification_args": [
                "--pure",
                "run",
                "--format",
                "json",
                "--model",
            ],
            "extra_env": {},
        },
    }


def test_load_opencode_manifest_rejects_legacy_verification_args(tmp_path: Path):
    manifest_path = tmp_path / "windows-stable-opencode.json"
    manifest_path.write_text(
        json.dumps(
            {
                "opencode_artifact": {
                    "id": "windows-opencode",
                    "url": "https://example.invalid/opencode.zip",
                    "sha256": "abc123",
                    "archive_type": "zip",
                    "required_files": ["opencode.exe"],
                    "required_file_sha256": {"opencode.exe": "def456"},
                    "install_subdir": "tools/opencode",
                    "launch": {
                        "executable_relative_path": "opencode.exe",
                        "verification_args": ["--pure", "models"],
                        "extra_env": {},
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="verification_args"):
        load_opencode_manifest(manifest_path)


def test_load_opencode_manifest_rejects_non_object_json_root(tmp_path: Path):
    manifest_path = tmp_path / "windows-stable-opencode.json"
    manifest_path.write_text("123", encoding="utf-8")

    with pytest.raises(ValueError, match="top-level object"):
        load_opencode_manifest(manifest_path)


def test_load_opencode_manifest_rejects_checksum_key_missing_from_required_files(
    tmp_path: Path,
):
    manifest_path = tmp_path / "windows-stable-opencode.json"
    manifest_path.write_text(
        json.dumps(
            {
                "opencode_artifact": {
                    "id": "windows-opencode",
                    "url": "https://example.invalid/opencode.zip",
                    "sha256": "abc123",
                    "archive_type": "zip",
                    "required_files": ["opencode.exe"],
                    "required_file_sha256": {"other.exe": "def456"},
                    "install_subdir": "tools/opencode",
                    "launch": {
                        "executable_relative_path": "opencode.exe",
                        "verification_args": [
                            "--pure",
                            "run",
                            "--format",
                            "json",
                            "--model",
                        ],
                        "extra_env": {},
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="required_file_sha256"):
        load_opencode_manifest(manifest_path)


def test_load_opencode_manifest_allows_presence_only_required_file_without_checksum(
    tmp_path: Path,
):
    manifest_path = tmp_path / "windows-stable-opencode.json"
    manifest_path.write_text(
        json.dumps(
            {
                "opencode_artifact": {
                    "id": "windows-opencode",
                    "url": "https://example.invalid/opencode.zip",
                    "sha256": "abc123",
                    "archive_type": "zip",
                    "required_files": ["opencode.exe", "support.dll"],
                    "required_file_sha256": {"opencode.exe": "def456"},
                    "install_subdir": "tools/opencode",
                    "launch": {
                        "executable_relative_path": "opencode.exe",
                        "verification_args": [
                            "--pure",
                            "run",
                            "--format",
                            "json",
                            "--model",
                        ],
                        "extra_env": {},
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    manifest = load_opencode_manifest(manifest_path)

    assert manifest["opencode_artifact"]["required_files"] == [
        "opencode.exe",
        "support.dll",
    ]
    assert manifest["opencode_artifact"]["required_file_sha256"] == {
        "opencode.exe": "def456"
    }
    assert (
        manifest["opencode_artifact"]["launch"]["executable_relative_path"]
        == "opencode.exe"
    )


def test_load_opencode_manifest_rejects_launch_executable_missing_from_required_files(
    tmp_path: Path,
):
    manifest_path = tmp_path / "windows-stable-opencode.json"
    manifest_path.write_text(
        json.dumps(
            {
                "opencode_artifact": {
                    "id": "windows-opencode",
                    "url": "https://example.invalid/opencode.zip",
                    "sha256": "abc123",
                    "archive_type": "zip",
                    "required_files": ["support.dll"],
                    "required_file_sha256": {},
                    "install_subdir": "tools/opencode",
                    "launch": {
                        "executable_relative_path": "opencode.exe",
                        "verification_args": ["--pure", "models"],
                        "extra_env": {},
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="executable_relative_path"):
        load_opencode_manifest(manifest_path)


def test_built_wheel_contains_opencode_manifest_json(tmp_path: Path):
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
            "local_ai_control_center_installer/manifests/windows-stable-opencode.json"
            in wheel_archive.namelist()
        )


def test_apply_opencode_bootstrap_skips_when_server_verification_not_ready(
    tmp_path: Path,
):
    session = InstallerSession(
        install_opencode=True,
        server_verification_status="failed",
        install_root=str(tmp_path / "install-root"),
        failing_step="server-verification",
        last_successful_step="active-model-config",
    )

    updated = apply_opencode_bootstrap(session, temp_root=tmp_path / "temp-runs")

    assert updated.opencode_artifact_status == "skipped"
    assert updated.opencode_verification_status == "skipped"
    assert updated.opencode_process_status == "skipped"
    assert updated.opencode_connection_status == "skipped"
    assert updated.failing_step == "server-verification"
    assert updated.last_successful_step == "active-model-config"


def test_apply_opencode_bootstrap_skips_when_install_opencode_is_false(
    tmp_path: Path,
):
    session = InstallerSession(
        install_opencode=False,
        server_verification_status="ready",
        install_root=str(tmp_path / "install-root"),
        verified_server_url="http://127.0.0.1:8080",
        active_model_config_path=str(tmp_path / "install-root" / "config" / "active-model.json"),
    )

    updated = apply_opencode_bootstrap(session, temp_root=tmp_path / "temp-runs")

    assert updated.opencode_artifact_status == "skipped"
    assert updated.opencode_verification_status == "skipped"
    assert updated.opencode_process_status == "skipped"
    assert updated.opencode_connection_status == "skipped"
    assert updated.failing_step is None


def test_apply_opencode_bootstrap_maps_manifest_load_error_to_opencode_manifest_failure(
    tmp_path: Path,
):
    session = InstallerSession(
        install_opencode=True,
        server_verification_status="ready",
        install_root=str(tmp_path / "install-root"),
        error_message="stale error",
    )

    updated = apply_opencode_bootstrap(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: (_ for _ in ()).throw(ValueError("bad manifest")),
    )

    assert updated.opencode_artifact_status == "failed"
    assert updated.opencode_verification_status == "skipped"
    assert updated.opencode_process_status == "skipped"
    assert updated.opencode_connection_status == "skipped"
    assert updated.failing_step == "opencode-manifest"
    assert updated.error_message == "bad manifest"


def test_apply_opencode_bootstrap_maps_missing_manifest_to_opencode_manifest_failure(
    tmp_path: Path,
):
    session = InstallerSession(
        install_opencode=True,
        server_verification_status="ready",
        install_root=str(tmp_path / "install-root"),
        error_message="stale error",
    )

    updated = apply_opencode_bootstrap(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: (_ for _ in ()).throw(FileNotFoundError("missing manifest")),
    )

    assert updated.opencode_artifact_status == "failed"
    assert updated.opencode_verification_status == "skipped"
    assert updated.opencode_process_status == "skipped"
    assert updated.opencode_connection_status == "skipped"
    assert updated.failing_step == "opencode-manifest"
    assert updated.error_message == "missing manifest"


def test_apply_opencode_bootstrap_marks_artifact_ready_when_valid_artifact_exists_and_managed_config_can_be_generated(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    artifact_root = install_root / "tools" / "opencode"
    artifact_root.mkdir(parents=True)
    (artifact_root / "opencode.exe").write_text("ok", encoding="utf-8")
    (artifact_root / "opencode-artifact.json").write_text(
        json.dumps(
            {
                "artifact_id": "windows-opencode",
                "source_sha256": "archive-sha",
            }
        ),
        encoding="utf-8",
    )
    active_model_config_path = _write_active_model_config(
        install_root / "config" / "active-model.json"
    )
    session = InstallerSession(
        install_opencode=True,
        server_verification_status="ready",
        install_root=str(install_root),
        verified_server_url="http://127.0.0.1:8080",
        active_model_config_path=str(active_model_config_path),
        error_message="stale error",
    )
    manifest = _build_opencode_manifest()

    updated = apply_opencode_bootstrap(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
    )

    managed_config_path = Path(updated.opencode_config_path)
    managed_config = json.loads(managed_config_path.read_text(encoding="utf-8"))

    assert updated.opencode_artifact_status == "ready"
    assert updated.opencode_verification_status == "skipped"
    assert updated.opencode_process_status == "skipped"
    assert updated.opencode_connection_status == "skipped"
    assert updated.opencode_artifact_id == "windows-opencode"
    assert updated.last_successful_step == "opencode-config"
    assert updated.error_message is None
    assert Path(updated.opencode_artifact_path) == artifact_root
    assert Path(updated.opencode_metadata_path) == artifact_root / "opencode-artifact.json"
    assert managed_config["installer_managed"] is True
    assert managed_config["autoupdate"] is False
    assert managed_config["model"] == "local-lacc/recommended-6gb"


def test_apply_opencode_bootstrap_fails_prerequisites_when_active_model_id_cannot_be_resolved(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    active_model_config_path = install_root / "config" / "active-model.json"
    active_model_config_path.parent.mkdir(parents=True, exist_ok=True)
    active_model_config_path.write_text(json.dumps({"model_path": "ignored"}), encoding="utf-8")
    session = InstallerSession(
        install_opencode=True,
        server_verification_status="ready",
        install_root=str(install_root),
        verified_server_url="http://127.0.0.1:8080",
        active_model_config_path=str(active_model_config_path),
        error_message="stale error",
    )
    manifest = _build_opencode_manifest()

    updated = apply_opencode_bootstrap(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
    )

    assert updated.opencode_artifact_status == "skipped"
    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_process_status == "skipped"
    assert updated.opencode_connection_status == "skipped"
    assert updated.failing_step == "opencode-verification-prerequisites"
    assert updated.error_message == "OpenCode bootstrap prerequisites are missing or invalid."


def test_apply_opencode_bootstrap_maps_archive_verification_failure_to_opencode_artifact(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    session = InstallerSession(
        install_opencode=True,
        server_verification_status="ready",
        install_root=str(install_root),
        verified_server_url="http://127.0.0.1:8080",
        active_model_config_path=str(
            _write_active_model_config(install_root / "config" / "active-model.json")
        ),
        error_message="stale error",
        download_plan=_opencode_download_plan(),
    )
    manifest = _build_opencode_manifest()

    def fake_download_archive(url: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"archive")
        return destination

    updated = apply_opencode_bootstrap(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        download_archive=fake_download_archive,
        verify_archive_sha256=lambda path, expected: False,
    )

    assert updated.opencode_artifact_status == "failed"
    assert updated.opencode_verification_status == "skipped"
    assert updated.opencode_process_status == "skipped"
    assert updated.opencode_connection_status == "skipped"
    assert updated.failing_step == "opencode-artifact"
    assert updated.error_message == "OpenCode archive checksum verification failed."


def test_apply_opencode_bootstrap_marks_opencode_config_failure_after_artifact_is_ready(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    artifact_root = install_root / "tools" / "opencode"
    artifact_root.mkdir(parents=True)
    (artifact_root / "opencode.exe").write_text("ok", encoding="utf-8")
    (artifact_root / "opencode-artifact.json").write_text(
        json.dumps(
            {
                "artifact_id": "windows-opencode",
                "source_sha256": "archive-sha",
            }
        ),
        encoding="utf-8",
    )
    session = InstallerSession(
        install_opencode=True,
        server_verification_status="ready",
        install_root=str(install_root),
        verified_server_url="http://127.0.0.1:8080",
        active_model_config_path=str(
            _write_active_model_config(install_root / "config" / "active-model.json")
        ),
        error_message="stale error",
    )
    manifest = _build_opencode_manifest()

    updated = apply_opencode_bootstrap(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        write_managed_config=lambda *args, **kwargs: (_ for _ in ()).throw(
            OSError("config failed")
        ),
    )

    assert updated.opencode_artifact_status == "ready"
    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_process_status == "skipped"
    assert updated.opencode_connection_status == "skipped"
    assert updated.last_successful_step == "opencode-artifact"
    assert updated.failing_step == "opencode-config"
    assert updated.error_message == "config failed"


def test_apply_opencode_bootstrap_generated_config_contains_local_lacc_provider_and_verified_server_url(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    session = InstallerSession(
        install_opencode=True,
        server_verification_status="ready",
        install_root=str(install_root),
        verified_server_url="http://127.0.0.1:8080",
        active_model_config_path=str(
            _write_active_model_config(
                install_root / "config" / "active-model.json",
                model_id="my-model-q4",
            )
        ),
        download_plan=_opencode_download_plan(),
    )
    manifest = _build_opencode_manifest()

    def fake_download_archive(url: str, destination: Path) -> Path:
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
        (destination_root / "opencode.exe").write_text("ok", encoding="utf-8")
        return destination_root

    updated = apply_opencode_bootstrap(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        download_archive=fake_download_archive,
        extract_archive=fake_extract_archive,
        verify_archive_sha256=lambda path, expected: True,
    )

    managed_config = json.loads(Path(updated.opencode_config_path).read_text(encoding="utf-8"))

    assert updated.opencode_artifact_status == "ready"
    assert managed_config["enabled_providers"] == ["local-lacc"]
    assert managed_config["providers"]["local-lacc"]["provider"] == "@ai-sdk/openai-compatible"
    assert managed_config["providers"]["local-lacc"]["options"]["baseURL"] == "http://127.0.0.1:8080/v1"
    assert managed_config["providers"]["local-lacc"]["models"] == {"my-model-q4": {}}


def test_apply_opencode_bootstrap_second_pass_reuses_staged_artifact_without_redownloading(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    session = InstallerSession(
        install_opencode=True,
        server_verification_status="ready",
        install_root=str(install_root),
        verified_server_url="http://127.0.0.1:8080",
        active_model_config_path=str(
            _write_active_model_config(
                install_root / "config" / "active-model.json",
                model_id="my-model-q4",
            )
        ),
        download_plan=_opencode_download_plan(),
    )
    manifest = _build_opencode_manifest()
    download_calls: list[tuple[str, Path]] = []

    def fake_download_archive(url: str, destination: Path) -> Path:
        download_calls.append((url, destination))
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
        (destination_root / "opencode.exe").write_text("ok", encoding="utf-8")
        return destination_root

    first_pass = apply_opencode_bootstrap(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        download_archive=fake_download_archive,
        extract_archive=fake_extract_archive,
        verify_archive_sha256=lambda path, expected: True,
    )

    assert first_pass.opencode_artifact_status == "ready"
    assert Path(first_pass.opencode_metadata_path).exists()
    assert len(download_calls) == 1

    second_pass = apply_opencode_bootstrap(
        InstallerSession(
            install_opencode=True,
            server_verification_status="ready",
            install_root=str(install_root),
            verified_server_url="http://127.0.0.1:8080",
            active_model_config_path=str(
                install_root / "config" / "active-model.json"
            ),
        ),
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        download_archive=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("should not redownload ready artifact")
        ),
    )

    assert second_pass.opencode_artifact_status == "ready"
    assert second_pass.last_successful_step == "opencode-config"


def test_apply_opencode_bootstrap_uses_session_download_plan_for_default_queue_item(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    session = InstallerSession(
        install_opencode=True,
        server_verification_status="ready",
        install_root=str(install_root),
        verified_server_url="http://127.0.0.1:8080",
        active_model_config_path=str(
            _write_active_model_config(
                install_root / "config" / "active-model.json",
                model_id="my-model-q4",
            )
        ),
        download_plan={
            "items": [
                {
                    "key": "opencode-artifact",
                    "label": "OpenCode",
                    "url": "https://example.invalid/opencode.zip",
                    "destination_hint": "tools/opencode",
                    "size_bytes": None,
                    "queue_index": 1,
                    "queue_total": 1,
                }
            ]
        },
    )
    manifest = _build_opencode_manifest()
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
        (destination_root / "opencode.exe").write_text("ok", encoding="utf-8")
        return destination_root

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_bootstrap._download_file",
        fake_shared_download,
    )

    updated = apply_opencode_bootstrap(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        extract_archive=fake_extract_archive,
        verify_archive_sha256=lambda path, expected: True,
    )

    assert updated.opencode_artifact_status == "ready"
    assert [item.label for item in planned_items] == ["OpenCode"]
