from local_ai_control_center_installer.session import DependencyRecord, InstallerSession


def test_installer_session_defaults_to_incomplete_product_status():
    session = InstallerSession()
    assert session.bootstrap_status == "failed"
    assert session.product_installation_status == "incomplete"


def test_dependency_record_serializes_user_decisions():
    record = DependencyRecord(
        name="git",
        required=True,
        detected=False,
        install_offered=True,
        user_accepted_install=False,
    )
    payload = record.to_dict()
    assert payload["name"] == "git"
    assert payload["user_accepted_install"] is False


def test_installer_session_serializes_first_slice_state():
    session = InstallerSession(
        bootstrap_status="ok",
        product_installation_status="failed",
        platform="windows",
        started_at="2026-05-20T22:45:00Z",
        existing_install_detected=True,
        install_mode="upgrade",
        install_root="C:\\AI",
        starter_model="qwen2.5-coder",
        install_opencode=True,
        attempt_turboquant=True,
        additional_model_paths=["D:\\models", "E:\\archive"],
        last_successful_step="download-model",
        failing_step="finalize-install",
        error_message="Disk full",
        dependencies=[
            DependencyRecord(
                name="git",
                required=True,
                detected=True,
                version="2.49.0",
                status="ready",
                install_offered=False,
                user_accepted_install=None,
                install_attempted=False,
                install_succeeded=None,
                blocking_reason=None,
            )
        ],
    )

    assert session.to_dict() == {
        "bootstrap_status": "ok",
        "product_installation_status": "failed",
        "platform": "windows",
        "started_at": "2026-05-20T22:45:00Z",
        "existing_install_detected": True,
        "install_mode": "upgrade",
        "install_root": "C:\\AI",
        "starter_model": "qwen2.5-coder",
        "install_opencode": True,
        "attempt_turboquant": True,
        "additional_model_paths": ["D:\\models", "E:\\archive"],
        "last_successful_step": "download-model",
        "failing_step": "finalize-install",
        "error_message": "Disk full",
        "dependencies": [
            {
                "name": "git",
                "required": True,
                "detected": True,
                "version": "2.49.0",
                "status": "ready",
                "install_offered": False,
                "user_accepted_install": None,
                "install_attempted": False,
                "install_succeeded": None,
                "blocking_reason": None,
            }
        ],
    }
