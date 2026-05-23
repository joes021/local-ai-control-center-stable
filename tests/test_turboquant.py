from hashlib import sha256
from pathlib import Path

from local_ai_control_center_installer.download_plan import DownloadPlan, DownloadPlanItem
from local_ai_control_center_installer.downloads import verify_sha256
from local_ai_control_center_installer.session import InstallerSession
from local_ai_control_center_installer import turboquant as turboquant_module
from local_ai_control_center_installer.turboquant import apply_turboquant


def _build_selected_session() -> InstallerSession:
    return InstallerSession(
        bootstrap_status="ready",
        runtime_payload_status="ready",
        server_verification_status="ready",
        opencode_artifact_status="ready",
        opencode_verification_status="ready",
        attempt_turboquant=True,
        install_root="C:\\LACC",
    )


def _strategy() -> dict:
    return {
        "artifact": {
            "id": "windows-turboquant-cuda12.4",
            "url": "https://example.invalid/turboquant.zip",
            "sha256": "turboquant-sha",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {
                "llama-server.exe": "2689367b205c16ce32ed4200942b8b8b1e262dfc70d9bc9fbc77c49699a4f1df"
            },
            "install_subdir": "tools/turboquant/windows-x64-cuda12.4",
            "size_bytes": 456,
            "launch": {"executable_relative_path": "llama-server.exe"},
        },
        "executable_relative_path": "llama-server.exe",
    }


def _sha256_hex(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _strategy_with_packaged_sidecars() -> dict:
    return {
        "artifact": {
            "id": "windows-turboquant-cuda12.4",
            "url": "https://example.invalid/turboquant.zip",
            "sha256": "turboquant-sha",
            "archive_type": "zip",
            "required_files": [
                "llama-server.exe",
                "libssl-3-x64.dll",
                "libcrypto-3-x64.dll",
            ],
            "required_file_sha256": {
                "llama-server.exe": _sha256_hex(b"server"),
                "libssl-3-x64.dll": _sha256_hex(b"ssl-dll"),
                "libcrypto-3-x64.dll": _sha256_hex(b"crypto-dll"),
            },
            "install_subdir": "tools/turboquant/windows-x64-cuda12.4",
            "size_bytes": 456,
            "launch": {"executable_relative_path": "llama-server.exe"},
            "packaged_sidecar_files": [
                "libssl-3-x64.dll",
                "libcrypto-3-x64.dll",
            ],
        },
        "executable_relative_path": "llama-server.exe",
    }


def test_apply_turboquant_marks_failed_with_error_when_selected_but_no_windows_strategy_exists():
    session = _build_selected_session()

    updated = apply_turboquant(
        session,
        resolve_windows_strategy=lambda: None,
    )

    assert updated.turboquant_status == "failed"
    assert (
        updated.turboquant_error
        == "No packaged Windows TurboQuant strategy is available in this installer build."
    )
    assert updated.failing_step is None
    assert updated.error_message is None


def test_apply_turboquant_marks_failed_with_explicit_support_error_when_packaged_path_is_unsupported():
    session = _build_selected_session()

    updated = apply_turboquant(
        session,
        resolve_windows_strategy=lambda: (_ for _ in ()).throw(
            ValueError(
                "Packaged TurboQuant currently supports only Windows x64 with an NVIDIA driver that exposes nvidia-smi."
            )
        ),
    )

    assert updated.turboquant_status == "failed"
    assert (
        updated.turboquant_error
        == "Packaged TurboQuant currently supports only Windows x64 with an NVIDIA driver that exposes nvidia-smi."
    )
    assert updated.failing_step is None
    assert updated.error_message is None


def test_apply_turboquant_marks_ready_when_selected_strategy_installs_successfully():
    session = _build_selected_session()

    updated = apply_turboquant(
        session,
        resolve_windows_strategy=lambda: _strategy(),
        install_strategy=lambda current_session, strategy: current_session,
    )

    assert updated.turboquant_status == "ready"
    assert updated.turboquant_error is None
    assert updated.turboquant_artifact_id == "windows-turboquant-cuda12.4"
    assert updated.turboquant_artifact_path.endswith("windows-x64-cuda12.4")
    assert updated.turboquant_metadata_path.endswith("turboquant-artifact.json")
    assert updated.turboquant_executable_path.endswith("llama-server.exe")


def test_apply_turboquant_skips_when_not_selected():
    session = InstallerSession(attempt_turboquant=False)

    updated = apply_turboquant(session)

    assert updated.turboquant_status == "skipped"
    assert updated.turboquant_error is None


def test_apply_turboquant_skips_when_core_prerequisites_are_not_ready():
    session = InstallerSession(
        bootstrap_status="failed",
        runtime_payload_status="skipped",
        attempt_turboquant=True,
    )

    updated = apply_turboquant(session)

    assert updated.turboquant_status == "skipped"
    assert updated.turboquant_error is None


def test_turboquant_artifact_is_not_ready_when_executable_imports_missing_sidecar_dlls(
    tmp_path: Path,
    monkeypatch,
):
    strategy = _strategy()
    artifact = strategy["artifact"]
    turboquant_root = tmp_path / artifact["install_subdir"]
    turboquant_root.mkdir(parents=True, exist_ok=True)
    (turboquant_root / "llama-server.exe").write_text("binary", encoding="utf-8")
    metadata_path = turboquant_root / "turboquant-artifact.json"

    monkeypatch.setattr(turboquant_module, "verify_required_files", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        turboquant_module,
        "verify_runtime_metadata",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        turboquant_module,
        "_verify_bundled_libraries_load",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        turboquant_module,
        "detect_missing_sidecar_imports",
        lambda path: ("libssl-3-x64.dll",),
        raising=False,
    )

    ready = turboquant_module._turboquant_artifact_ready(
        turboquant_root,
        metadata_path,
        artifact,
        verify_required_file_checksums=lambda *args, **kwargs: True,
    )

    assert ready is False


def test_turboquant_artifact_ready_hydrates_packaged_sidecars_for_existing_install(
    tmp_path: Path,
    monkeypatch,
):
    strategy = _strategy_with_packaged_sidecars()
    artifact = strategy["artifact"]
    turboquant_root = tmp_path / artifact["install_subdir"]
    turboquant_root.mkdir(parents=True, exist_ok=True)
    (turboquant_root / "llama-server.exe").write_bytes(b"server")
    metadata_path = turboquant_root / "turboquant-artifact.json"

    sidecar_root = tmp_path / "packaged-sidecars"
    sidecar_root.mkdir(parents=True, exist_ok=True)
    (sidecar_root / "libssl-3-x64.dll").write_bytes(b"ssl-dll")
    (sidecar_root / "libcrypto-3-x64.dll").write_bytes(b"crypto-dll")

    monkeypatch.setattr(
        turboquant_module,
        "_resolve_packaged_sidecar_root",
        lambda current_artifact: sidecar_root,
        raising=False,
    )
    monkeypatch.setattr(
        turboquant_module,
        "verify_runtime_metadata",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        turboquant_module,
        "_verify_bundled_libraries_load",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        turboquant_module,
        "detect_missing_sidecar_imports",
        lambda path: tuple(
            missing
            for missing in ("libssl-3-x64.dll", "libcrypto-3-x64.dll")
            if not (path.parent / missing).is_file()
        ),
        raising=False,
    )

    ready = turboquant_module._turboquant_artifact_ready(
        turboquant_root,
        metadata_path,
        artifact,
        verify_required_file_checksums=lambda root, mapping: all(
            verify_sha256(root / relative_path, checksum)
            for relative_path, checksum in mapping.items()
        ),
    )

    assert ready is True
    assert (turboquant_root / "libssl-3-x64.dll").read_bytes() == b"ssl-dll"
    assert (turboquant_root / "libcrypto-3-x64.dll").read_bytes() == b"crypto-dll"


def test_apply_turboquant_installs_packaged_sidecars_when_upstream_archive_omits_them(
    tmp_path: Path,
    monkeypatch,
):
    strategy = _strategy_with_packaged_sidecars()
    artifact = strategy["artifact"]
    install_root = tmp_path / "install-root"
    session = InstallerSession(
        bootstrap_status="ready",
        runtime_payload_status="ready",
        server_verification_status="ready",
        opencode_artifact_status="ready",
        opencode_verification_status="ready",
        attempt_turboquant=True,
        install_root=str(install_root),
        download_plan=DownloadPlan(
            items=(
                DownloadPlanItem(
                    key="turboquant-artifact",
                    label="TurboQuant",
                    url=artifact["url"],
                    destination_hint=artifact["install_subdir"],
                    size_bytes=artifact["size_bytes"],
                    queue_index=1,
                    queue_total=1,
                ),
            )
        ),
    )

    sidecar_root = tmp_path / "packaged-sidecars"
    sidecar_root.mkdir(parents=True, exist_ok=True)
    (sidecar_root / "libssl-3-x64.dll").write_bytes(b"ssl-dll")
    (sidecar_root / "libcrypto-3-x64.dll").write_bytes(b"crypto-dll")

    monkeypatch.setattr(
        turboquant_module,
        "_resolve_packaged_sidecar_root",
        lambda current_artifact: sidecar_root,
        raising=False,
    )
    monkeypatch.setattr(
        turboquant_module,
        "_verify_bundled_libraries_load",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        turboquant_module,
        "detect_missing_sidecar_imports",
        lambda path: tuple(
            missing
            for missing in ("libssl-3-x64.dll", "libcrypto-3-x64.dll")
            if not (path.parent / missing).is_file()
        ),
        raising=False,
    )

    def _download_archive(url: str, destination: Path, **_kwargs) -> Path:
        destination.write_bytes(b"archive")
        return destination

    def _extract_archive(_archive_path: Path, extracted_root: Path, *, archive_type: str) -> None:
        assert archive_type == "zip"
        extracted_root.mkdir(parents=True, exist_ok=True)
        (extracted_root / "llama-server.exe").write_bytes(b"server")

    updated = apply_turboquant(
        session,
        temp_root=tmp_path / "temp",
        resolve_windows_strategy=lambda: strategy,
        download_archive=_download_archive,
        extract_archive=_extract_archive,
        verify_archive_sha256=lambda *args, **kwargs: True,
        verify_required_file_checksums=lambda root, mapping: all(
            verify_sha256(root / relative_path, checksum)
            for relative_path, checksum in mapping.items()
        ),
    )

    turboquant_root = install_root / artifact["install_subdir"]
    assert updated.turboquant_status == "ready"
    assert (turboquant_root / "libssl-3-x64.dll").read_bytes() == b"ssl-dll"
    assert (turboquant_root / "libcrypto-3-x64.dll").read_bytes() == b"crypto-dll"
