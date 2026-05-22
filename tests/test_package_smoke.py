from local_ai_control_center_installer.main import run_installer


def test_run_installer_smoke_with_injected_collaborators():
    def collect_answers(session):
        session.install_opencode = True
        return session

    def apply_phase(session):
        session.bootstrap_status = "ready"
        return session

    def apply_runtime_payload(session):
        session.runtime_payload_status = "ready"
        session.runtime_artifact_status = "ready"
        session.starter_model_status = "ready"
        session.active_model_config_status = "ready"
        session.model_locations_config_status = "ready"
        session.runtime_endpoint_config_status = "ready"
        return session

    def apply_server_verification(session):
        session.server_verification_status = "ready"
        session.server_process_status = "ready"
        session.server_health_status = "ready"
        return session

    def apply_opencode_bootstrap(session):
        session.opencode_artifact_status = "ready"
        return session

    def apply_opencode_verification(session):
        session.opencode_verification_status = "ready"
        session.opencode_process_status = "ready"
        session.opencode_connection_status = "ready"
        return session

    def apply_first_run_validation(session):
        session.first_run_status = "ready"
        session.first_run_process_status = "ready"
        session.first_run_connection_status = "ready"
        return session

    def apply_product_gate(session):
        session.product_installation_status = "complete"
        return session

    result = run_installer(
        collect_answers=collect_answers,
        scan_dependencies=lambda session: session,
        apply_phase=apply_phase,
        apply_runtime_payload=apply_runtime_payload,
        apply_server_verification=apply_server_verification,
        apply_opencode_bootstrap=apply_opencode_bootstrap,
        apply_opencode_verification=apply_opencode_verification,
        apply_turboquant=lambda session: session,
        apply_first_run_validation=apply_first_run_validation,
        apply_product_gate=apply_product_gate,
        write_reports=lambda session: None,
    )

    assert result["product_installation_status"] == "complete"
