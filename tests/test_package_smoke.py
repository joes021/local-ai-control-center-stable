from local_ai_control_center_installer.main import run_installer


def test_run_installer_returns_placeholder_result():
    result = run_installer()
    assert result["product_installation_status"] == "incomplete"
