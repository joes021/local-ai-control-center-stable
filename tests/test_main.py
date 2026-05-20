import pytest

import local_ai_control_center_installer.main as main_module
from local_ai_control_center_installer.main import run_installer
from local_ai_control_center_installer.prompts import PromptCancelledError
from local_ai_control_center_installer.session import InstallerSession


def test_run_installer_confirms_summary_before_dependency_scan():
    events: list[str] = []

    def fake_collect(session, **_):
        events.append("summary-confirm")
        return session

    def fake_scan(session, **_):
        events.append("scan")
        return session

    run_installer(
        collect_answers=fake_collect,
        scan_dependencies=fake_scan,
        apply_phase=lambda session: session,
        write_reports=lambda session: None,
    )

    assert events == ["summary-confirm", "scan"]


def test_run_installer_stops_before_dependency_scan_when_confirmation_is_cancelled():
    events: list[str] = []

    def fake_collect(session, **_):
        events.append("confirm")
        raise PromptCancelledError("Installer questionnaire cancelled.")

    def fake_scan(session, **_):
        events.append("scan")
        return session

    def fake_apply(session, **_):
        events.append("apply")
        return session

    def fake_write_reports(session, **_):
        events.append("report")

    with pytest.raises(PromptCancelledError):
        run_installer(
            collect_answers=fake_collect,
            scan_dependencies=fake_scan,
            apply_phase=fake_apply,
            write_reports=fake_write_reports,
        )

    assert events == ["confirm"]


def test_run_installer_writes_reports_after_failed_bootstrap_apply():
    events: list[str] = []
    written_payloads: list[dict] = []

    def fake_collect(session, **_):
        events.append("collect")
        return session

    def fake_scan(session, **_):
        events.append("scan")
        return session

    def fake_apply(session: InstallerSession, **_):
        events.append("apply")
        session.bootstrap_status = "failed"
        session.failing_step = "dependency-bootstrap"
        return session

    def fake_write_reports(session: InstallerSession, **_):
        events.append("report")
        written_payloads.append(session.to_dict())

    run_installer(
        collect_answers=fake_collect,
        scan_dependencies=fake_scan,
        apply_phase=fake_apply,
        write_reports=fake_write_reports,
    )

    assert events == ["collect", "scan", "apply", "report"]
    assert written_payloads == [
        {
            "bootstrap_status": "failed",
            "product_installation_status": "incomplete",
            "platform": written_payloads[0]["platform"],
            "started_at": written_payloads[0]["started_at"],
            "existing_install_detected": False,
            "install_mode": None,
            "install_root": None,
            "starter_model": None,
            "install_opencode": False,
            "attempt_turboquant": False,
            "additional_model_paths": [],
            "last_successful_step": None,
            "failing_step": "dependency-bootstrap",
            "error_message": None,
            "dependencies": [],
        }
    ]


def test_run_installer_returns_final_session_payload():
    def fake_apply(session: InstallerSession, **_):
        session.bootstrap_status = "failed"
        session.failing_step = "dependency-bootstrap"
        return session

    result = run_installer(
        collect_answers=lambda session, **_: session,
        scan_dependencies=lambda session, **_: session,
        apply_phase=fake_apply,
        write_reports=lambda session, **_: None,
    )

    assert result["bootstrap_status"] == "failed"
    assert result["failing_step"] == "dependency-bootstrap"


def test_run_installer_uses_default_collaborators_when_none_are_injected(
    monkeypatch: pytest.MonkeyPatch,
):
    events: list[str] = []

    def fake_collect(session: InstallerSession):
        events.append("collect")
        return session

    def fake_scan(session: InstallerSession):
        events.append("scan")
        return session

    def fake_apply(session: InstallerSession):
        events.append("apply")
        return session

    def fake_write_reports(session: InstallerSession):
        del session
        events.append("report")

    monkeypatch.setattr(main_module, "default_collect_answers", fake_collect, raising=False)
    monkeypatch.setattr(main_module, "default_scan_dependencies", fake_scan, raising=False)
    monkeypatch.setattr(main_module, "default_apply_phase", fake_apply, raising=False)
    monkeypatch.setattr(main_module, "default_write_reports", fake_write_reports, raising=False)

    run_installer()

    assert events == ["collect", "scan", "apply", "report"]
