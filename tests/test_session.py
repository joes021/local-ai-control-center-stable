from local_ai_control_center_installer.session import DependencyRecord, InstallerSession

TEST_MARKER = "LACC_VERIFY_MARKER:test-marker"
TEST_VERIFIED_OPENCODE_COMMAND = (
    "opencode --pure run --format json --model "
    f'local-lacc/recommended-6gb "Repeat this exact token once: {TEST_MARKER}"'
)


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
        starter_model="recommended-12gb",
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
        "runtime_payload_status": "skipped",
        "runtime_artifact_status": "skipped",
        "starter_model_status": "skipped",
        "active_model_config_status": "skipped",
        "model_locations_config_status": "skipped",
        "runtime_endpoint_config_status": "skipped",
        "server_verification_status": "skipped",
        "server_process_status": "skipped",
        "server_health_status": "skipped",
        "opencode_artifact_status": "skipped",
        "opencode_verification_status": "skipped",
        "opencode_process_status": "skipped",
        "opencode_connection_status": "skipped",
        "platform": "windows",
        "started_at": "2026-05-20T22:45:00Z",
        "existing_install_detected": True,
        "install_mode": "upgrade",
        "install_root": "C:\\AI",
        "runtime_artifact_id": None,
        "runtime_artifact_path": None,
        "starter_model": "recommended-12gb",
        "starter_model_path": None,
        "active_model_config_path": None,
        "model_locations_config_path": None,
        "runtime_metadata_path": None,
        "runtime_endpoint_config_path": None,
        "opencode_artifact_id": None,
        "opencode_artifact_path": None,
        "opencode_metadata_path": None,
        "opencode_config_path": None,
        "verified_opencode_command": None,
        "managed_runtime_port": None,
        "verified_server_port": None,
        "verified_server_url": None,
        "opencode_log_path": None,
        "server_log_path": None,
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


def test_installer_session_serializes_runtime_payload_fields():
    session = InstallerSession(
        runtime_payload_status="ready",
        runtime_artifact_status="ready",
        starter_model="recommended-6gb",
        starter_model_status="ready",
        active_model_config_status="ready",
        model_locations_config_status="ready",
        runtime_endpoint_config_status="ready",
        runtime_artifact_id="windows-llama-cpp-runtime",
        runtime_artifact_path="C:\\LACC\\runtime\\llama.cpp",
        starter_model_path="C:\\LACC\\models\\recommended-6gb\\recommended-6gb.gguf",
        active_model_config_path="C:\\LACC\\config\\active-model.json",
        model_locations_config_path="C:\\LACC\\config\\model-locations.json",
        runtime_metadata_path="C:\\LACC\\runtime\\llama.cpp\\runtime-artifact.json",
        runtime_endpoint_config_path="C:\\LACC\\config\\runtime-endpoint.json",
        managed_runtime_port=39281,
    )

    payload = session.to_dict()

    assert payload["runtime_payload_status"] == "ready"
    assert payload["runtime_artifact_status"] == "ready"
    assert payload["starter_model"] == "recommended-6gb"
    assert payload["starter_model_status"] == "ready"
    assert payload["active_model_config_status"] == "ready"
    assert payload["model_locations_config_status"] == "ready"
    assert payload["runtime_endpoint_config_status"] == "ready"
    assert payload["runtime_artifact_id"] == "windows-llama-cpp-runtime"
    assert payload["runtime_artifact_path"] == "C:\\LACC\\runtime\\llama.cpp"
    assert payload["starter_model_path"].endswith("recommended-6gb.gguf")
    assert payload["active_model_config_path"] == "C:\\LACC\\config\\active-model.json"
    assert payload["model_locations_config_path"] == "C:\\LACC\\config\\model-locations.json"
    assert payload["runtime_metadata_path"].endswith("runtime-artifact.json")
    assert payload["runtime_endpoint_config_path"] == "C:\\LACC\\config\\runtime-endpoint.json"
    assert payload["managed_runtime_port"] == 39281


def test_installer_session_serializes_server_verification_fields():
    session = InstallerSession(
        server_verification_status="ready",
        server_process_status="ready",
        server_health_status="ready",
        verified_server_port=8080,
        verified_server_url="http://127.0.0.1:8080",
        server_log_path="C:\\LACC\\temp\\llama-server.log",
    )

    payload = session.to_dict()

    assert payload["server_verification_status"] == "ready"
    assert payload["server_process_status"] == "ready"
    assert payload["server_health_status"] == "ready"
    assert payload["verified_server_port"] == 8080
    assert payload["verified_server_url"] == "http://127.0.0.1:8080"
    assert payload["server_log_path"] == "C:\\LACC\\temp\\llama-server.log"


def test_installer_session_serializes_opencode_fields():
    session = InstallerSession(
        opencode_artifact_status="ready",
        opencode_verification_status="failed",
        opencode_process_status="ready",
        opencode_connection_status="failed",
        opencode_artifact_id="opencode-windows-x64",
        opencode_artifact_path="C:\\LACC\\opencode",
        opencode_metadata_path="C:\\LACC\\opencode\\opencode-artifact.json",
        opencode_config_path="C:\\LACC\\config\\opencode.json",
        verified_opencode_command=TEST_VERIFIED_OPENCODE_COMMAND,
        opencode_log_path="C:\\LACC\\temp\\opencode-verification.log",
    )

    payload = session.to_dict()

    assert payload["opencode_artifact_status"] == "ready"
    assert payload["opencode_verification_status"] == "failed"
    assert payload["opencode_process_status"] == "ready"
    assert payload["opencode_connection_status"] == "failed"
    assert payload["opencode_artifact_id"] == "opencode-windows-x64"
    assert payload["opencode_artifact_path"] == "C:\\LACC\\opencode"
    assert payload["opencode_metadata_path"].endswith("opencode-artifact.json")
    assert payload["opencode_config_path"] == "C:\\LACC\\config\\opencode.json"
    assert payload["verified_opencode_command"] == TEST_VERIFIED_OPENCODE_COMMAND
    assert payload["opencode_log_path"] == "C:\\LACC\\temp\\opencode-verification.log"
