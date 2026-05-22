from local_ai_control_center_installer.session import InstallerSession
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
