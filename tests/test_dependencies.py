from local_ai_control_center_installer.dependencies import (
    apply_dependency_decision,
    evaluate_dependency,
    scan_all_dependencies,
)
from local_ai_control_center_installer.session import InstallerSession


def test_evaluate_dependency_marks_present_tool_as_ready():
    record = evaluate_dependency("git", required=True, detected_version="2.49.0")
    assert record.status == "ready"
    assert record.detected is True


def test_evaluate_dependency_marks_missing_required_tool_as_installable():
    record = evaluate_dependency("node", required=True, detected_version=None)
    assert record.status == "missing-installable"
    assert record.install_offered is True


def test_apply_dependency_decision_marks_declined_required_dependency_as_blocking():
    record = evaluate_dependency("node", required=True, detected_version=None)

    updated = apply_dependency_decision(
        record,
        user_accepts_install=False,
        install_fn=lambda dependency: True,
    )

    assert updated.user_accepted_install is False
    assert updated.status == "missing-blocking"
    assert "server cannot be used reliably" in updated.blocking_reason


def test_apply_dependency_decision_marks_failed_install_attempt():
    record = evaluate_dependency("node", required=True, detected_version=None)

    updated = apply_dependency_decision(
        record,
        user_accepts_install=True,
        install_fn=lambda dependency: False,
    )

    assert updated.user_accepted_install is True
    assert updated.install_attempted is True
    assert updated.install_succeeded is False
    assert updated.status == "failed-install"


def test_build_tools_failure_explains_server_startup_is_not_usable():
    record = evaluate_dependency("build-tools", required=True, detected_version=None)

    updated = apply_dependency_decision(
        record,
        user_accepts_install=False,
        install_fn=lambda dependency: True,
    )

    assert updated.status == "missing-blocking"
    assert "server startup" in updated.blocking_reason
    assert "cannot be used reliably" in updated.blocking_reason


def test_scan_all_dependencies_populates_required_dependency_records():
    session = InstallerSession()

    updated = scan_all_dependencies(
        session,
        probes={
            "python": lambda: "3.13.7",
            "git": lambda: "2.49.0",
            "node": lambda: None,
            "build-tools": lambda: None,
        },
    )

    assert updated is session
    assert [record.name for record in updated.dependencies] == [
        "python",
    ]
    assert [record.status for record in updated.dependencies] == [
        "ready",
    ]
