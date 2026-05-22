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
    )


def test_apply_turboquant_marks_failed_with_error_when_selected_but_no_windows_strategy_exists():
    session = _build_selected_session()

    updated = apply_turboquant(session)

    assert updated.turboquant_status == "failed"
    assert (
        updated.turboquant_error
        == "No supported Windows TurboQuant install path is currently packaged."
    )
    assert updated.failing_step is None
    assert updated.error_message is None


def test_apply_turboquant_marks_ready_when_selected_strategy_installs_successfully():
    session = _build_selected_session()

    updated = apply_turboquant(
        session,
        resolve_windows_strategy=lambda: {"id": "turboquant-win-x64"},
        install_strategy=lambda current_session, strategy: current_session,
    )

    assert updated.turboquant_status == "ready"
    assert updated.turboquant_error is None


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
