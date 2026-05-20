import pytest

import local_ai_control_center_installer.defaults as defaults_module
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


def test_run_installer_uses_real_default_adapters_when_none_are_injected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    events: list[str] = []
    written_reports: list[tuple[str, str]] = []

    def fake_collect_installer_answers(session: InstallerSession):
        events.append("collect")
        session.install_root = str(tmp_path / "install-root")
        return session

    def fake_probe_python_version():
        events.append("probe-python")
        return "3.13.7"

    def fake_probe_git_version():
        events.append("probe-git")
        return "git version 2.49.0.windows.1"

    def fake_probe_node_version():
        events.append("probe-node")
        return "v22.14.0"

    def fake_probe_build_tools_version():
        events.append("probe-build-tools")
        return "cmake version 3.31.6"

    def fake_apply_bootstrap_phase(session: InstallerSession, temp_root):
        events.append("apply")
        assert temp_root == tmp_path / "temp-runs"
        session.bootstrap_status = "ready"
        session.failing_step = None
        return session

    def fake_write_human_log(session: InstallerSession, log_path):
        events.append("write-log")
        written_reports.append(("log", str(log_path)))
        return log_path

    def fake_write_json_report(session: InstallerSession, report_path):
        events.append("write-json")
        written_reports.append(("json", str(report_path)))
        return report_path

    monkeypatch.setattr(defaults_module, "collect_installer_answers", fake_collect_installer_answers)
    monkeypatch.setattr(defaults_module, "_probe_python_version", fake_probe_python_version)
    monkeypatch.setattr(defaults_module, "_probe_git_version", fake_probe_git_version)
    monkeypatch.setattr(defaults_module, "_probe_node_version", fake_probe_node_version)
    monkeypatch.setattr(defaults_module, "_probe_build_tools_version", fake_probe_build_tools_version)
    monkeypatch.setattr(defaults_module, "apply_bootstrap_phase", fake_apply_bootstrap_phase)
    monkeypatch.setattr(defaults_module, "write_human_log", fake_write_human_log)
    monkeypatch.setattr(defaults_module, "write_json_report", fake_write_json_report)
    monkeypatch.setattr(defaults_module, "_default_temp_root", lambda: tmp_path / "temp-runs")

    result = run_installer()

    assert events == [
        "collect",
        "probe-python",
        "probe-git",
        "probe-node",
        "probe-build-tools",
        "apply",
        "write-log",
        "write-json",
    ]
    assert [dependency["version"] for dependency in result["dependencies"]] == [
        "3.13.7",
        "git version 2.49.0.windows.1",
        "v22.14.0",
        "cmake version 3.31.6",
    ]
    assert written_reports == [
        ("log", str(tmp_path / "temp-runs" / "LocalAIControlCenterInstaller" / "runs" / result["started_at"].replace(":", "-") / "install.log")),
        ("json", str(tmp_path / "temp-runs" / "LocalAIControlCenterInstaller" / "runs" / result["started_at"].replace(":", "-") / "install-report.json")),
    ]
