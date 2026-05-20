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
