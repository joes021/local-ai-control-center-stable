from __future__ import annotations

from local_ai_control_center_installer.session import InstallerSession


def apply_product_gate(session: InstallerSession) -> InstallerSession:
    failure_message = _build_failure_message(session)
    if failure_message is None:
        session.product_installation_status = "complete"
        session.failing_step = None
        session.error_message = None
        return session

    session.product_installation_status = "failed"
    if session.failing_step is None:
        session.failing_step = "product-gate"
        session.error_message = failure_message
        return session
    if session.failing_step == "product-gate":
        session.error_message = failure_message
    return session


def _build_failure_message(session: InstallerSession) -> str | None:
    if session.install_opencode is not True:
        return "OpenCode is required for a successful installation."

    checks = (
        ("bootstrap_status", "ready", "The bootstrap phase did not finish ready."),
        ("runtime_payload_status", "ready", "The runtime payload is not ready."),
        ("runtime_artifact_status", "ready", "The runtime artifact is not ready."),
        ("starter_model_status", "ready", "The starter model is not ready."),
        (
            "active_model_config_status",
            "ready",
            "The installer did not persist a ready active-model configuration.",
        ),
        (
            "model_locations_config_status",
            "ready",
            "The installer did not persist a ready model-locations configuration.",
        ),
        (
            "runtime_endpoint_config_status",
            "ready",
            "The installer did not persist a ready runtime-endpoint configuration.",
        ),
        (
            "server_verification_status",
            "ready",
            "The local runtime server was not verified ready.",
        ),
        (
            "server_process_status",
            "ready",
            "The local runtime server process was not verified ready.",
        ),
        (
            "server_health_status",
            "ready",
            "The local runtime health check was not verified ready.",
        ),
        (
            "opencode_artifact_status",
            "ready",
            "The OpenCode artifact is not ready.",
        ),
        (
            "opencode_verification_status",
            "ready",
            "OpenCode live-route verification did not finish ready.",
        ),
        (
            "opencode_process_status",
            "ready",
            "OpenCode process verification did not finish ready.",
        ),
        (
            "opencode_connection_status",
            "ready",
            "OpenCode live-route verification did not confirm a ready connection.",
        ),
        ("first_run_status", "ready", "The first-run OpenCode smoke did not finish ready."),
        (
            "first_run_process_status",
            "ready",
            "The first-run OpenCode process did not finish ready.",
        ),
        (
            "first_run_connection_status",
            "ready",
            "The first-run OpenCode smoke did not confirm a ready connection.",
        ),
        (
            "control_center_runtime_status",
            "ready",
            "The control panel runtime is not ready.",
        ),
        (
            "control_center_launch_status",
            "ready",
            "The control panel did not launch ready.",
        ),
    )

    for field_name, expected, message in checks:
        if getattr(session, field_name) != expected:
            return message
    return None
