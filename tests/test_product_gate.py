from local_ai_control_center_installer.product_gate import apply_product_gate
from local_ai_control_center_installer.session import InstallerSession


def _build_gate_ready_session() -> InstallerSession:
    return InstallerSession(
        bootstrap_status="ready",
        runtime_payload_status="ready",
        runtime_artifact_status="ready",
        starter_model_status="ready",
        active_model_config_status="ready",
        model_locations_config_status="ready",
        runtime_endpoint_config_status="ready",
        server_verification_status="ready",
        server_process_status="ready",
        server_health_status="ready",
        opencode_artifact_status="ready",
        opencode_verification_status="ready",
        opencode_process_status="ready",
        opencode_connection_status="ready",
        first_run_status="ready",
        first_run_process_status="ready",
        first_run_connection_status="ready",
        control_center_runtime_status="ready",
        control_center_launch_status="ready",
        install_opencode=True,
    )


def test_apply_product_gate_marks_complete_only_when_all_required_statuses_are_ready():
    session = _build_gate_ready_session()

    updated = apply_product_gate(session)

    assert updated.product_installation_status == "complete"
    assert updated.failing_step is None
    assert updated.error_message is None


def test_apply_product_gate_marks_failed_when_opencode_was_declined():
    session = _build_gate_ready_session()
    session.install_opencode = False

    updated = apply_product_gate(session)

    assert updated.product_installation_status == "failed"
    assert updated.failing_step == "product-gate"
    assert updated.error_message == "OpenCode is required for a successful installation."


def test_apply_product_gate_marks_failed_when_model_locations_config_is_not_ready():
    session = _build_gate_ready_session()
    session.model_locations_config_status = "failed"

    updated = apply_product_gate(session)

    assert updated.product_installation_status == "failed"
    assert updated.failing_step == "product-gate"
    assert (
        updated.error_message
        == "The installer did not persist a ready model-locations configuration."
    )


def test_apply_product_gate_marks_failed_when_runtime_endpoint_config_is_not_ready():
    session = _build_gate_ready_session()
    session.runtime_endpoint_config_status = "failed"

    updated = apply_product_gate(session)

    assert updated.product_installation_status == "failed"
    assert updated.failing_step == "product-gate"
    assert (
        updated.error_message
        == "The installer did not persist a ready runtime-endpoint configuration."
    )


def test_apply_product_gate_allows_complete_when_turboquant_is_the_only_failure():
    session = _build_gate_ready_session()
    session.turboquant_status = "failed"
    session.turboquant_error = (
        "No supported Windows TurboQuant install path is currently packaged."
    )

    updated = apply_product_gate(session)

    assert updated.product_installation_status == "complete"
    assert updated.failing_step is None
    assert updated.error_message is None


def test_apply_product_gate_marks_failed_when_control_center_launch_is_not_ready():
    session = _build_gate_ready_session()
    session.control_center_launch_status = "failed"

    updated = apply_product_gate(session)

    assert updated.product_installation_status == "failed"
    assert updated.failing_step == "product-gate"
    assert updated.error_message == "The control panel did not launch ready."
