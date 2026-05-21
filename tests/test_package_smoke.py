from local_ai_control_center_installer.main import run_installer


def test_run_installer_smoke_with_injected_collaborators():
    result = run_installer(
        collect_answers=lambda session: session,
        scan_dependencies=lambda session: session,
        apply_phase=lambda session: session,
        apply_runtime_payload=lambda session: session,
        apply_server_verification=lambda session: session,
        write_reports=lambda session: None,
    )

    assert result["product_installation_status"] == "incomplete"
