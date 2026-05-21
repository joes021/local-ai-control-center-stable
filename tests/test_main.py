import json
import subprocess

import pytest

import local_ai_control_center_installer.defaults as defaults_module
import local_ai_control_center_installer.main as main_module
from local_ai_control_center_installer.main import run_installer
from local_ai_control_center_installer.prompts import PromptCancelledError
from local_ai_control_center_installer.session import InstallerSession


def test_main_delegates_to_run_installer_and_returns_zero(monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []

    def fake_run_installer():
        calls.append("run")
        return {"bootstrap_status": "ready"}

    monkeypatch.setattr(main_module, "run_installer", fake_run_installer)

    assert main_module.main() == 0
    assert calls == ["run"]


def test_main_returns_non_zero_when_prompt_is_cancelled(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    def fake_run_installer():
        raise PromptCancelledError("Installer questionnaire cancelled.")

    monkeypatch.setattr(main_module, "run_installer", fake_run_installer)

    assert main_module.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Installer questionnaire cancelled.\n"


def test_main_returns_non_zero_when_bootstrap_status_is_failed(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_run_installer():
        return {"bootstrap_status": "failed"}

    monkeypatch.setattr(main_module, "run_installer", fake_run_installer)

    assert main_module.main() == 1


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
            "runtime_payload_status": "skipped",
            "runtime_artifact_status": "skipped",
            "starter_model_status": "skipped",
            "active_model_config_status": "skipped",
            "platform": written_payloads[0]["platform"],
            "started_at": written_payloads[0]["started_at"],
            "existing_install_detected": False,
            "install_mode": None,
            "install_root": None,
            "runtime_artifact_id": None,
            "runtime_artifact_path": None,
            "starter_model": None,
            "starter_model_path": None,
            "active_model_config_path": None,
            "runtime_metadata_path": None,
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


def test_probe_node_version_requires_both_node_and_npm(
    monkeypatch: pytest.MonkeyPatch,
):
    versions = {
        ("node", "--version"): "v22.14.0",
        ("npm", "--version"): "10.9.2",
    }
    availability = {
        "node": "C:\\Tools\\node.exe",
        "npm": None,
    }

    monkeypatch.setattr(defaults_module.shutil, "which", lambda name: availability.get(name))
    monkeypatch.setattr(
        defaults_module,
        "_capture_first_output_line",
        lambda command: versions.get(tuple(command)),
    )

    assert defaults_module._probe_node_version() is None

    availability["npm"] = "C:\\Tools\\npm.cmd"

    assert defaults_module._probe_node_version() == "v22.14.0; npm 10.9.2"


def test_probe_build_tools_version_requires_compiler_and_build_driver(
    monkeypatch: pytest.MonkeyPatch,
):
    versions = {
        ("gcc", "--version"): "gcc (GCC) 14.2.0",
        ("cmake", "--version"): "cmake version 3.31.6",
    }
    availability = {
        "cl": None,
        "gcc": None,
        "clang": None,
        "cmake": "C:\\Tools\\cmake.exe",
        "nmake": None,
        "make": None,
    }

    monkeypatch.setattr(defaults_module.shutil, "which", lambda name: availability.get(name))
    monkeypatch.setattr(
        defaults_module,
        "_capture_first_available_build_tool_output",
        lambda *commands: next(
            (
                versions.get(tuple(command))
                for command in commands
                if availability.get(command[0]) and versions.get(tuple(command))
            ),
            None,
        ),
    )
    monkeypatch.setattr(
        defaults_module,
        "_capture_first_output_line",
        lambda command: versions.get(tuple(command)),
    )

    assert defaults_module._probe_build_tools_version() is None

    availability["gcc"] = "C:\\Tools\\gcc.exe"

    assert (
        defaults_module._probe_build_tools_version()
        == "gcc (GCC) 14.2.0; cmake version 3.31.6"
    )


def test_probe_node_version_rejects_non_zero_stderr_banner(
    monkeypatch: pytest.MonkeyPatch,
):
    availability = {
        "node": "C:\\Tools\\node.exe",
        "npm": "C:\\Tools\\npm.cmd",
    }

    def fake_run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        if tuple(command) == ("node", "--version"):
            return subprocess.CompletedProcess(
                command,
                1,
                stdout="",
                stderr="node is not recognized as an internal or external command\n",
            )
        if tuple(command) == ("npm", "--version"):
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="10.9.2\n",
                stderr="",
            )
        raise AssertionError(f"Unexpected command: {command!r}")

    monkeypatch.setattr(defaults_module.shutil, "which", lambda name: availability.get(name))
    monkeypatch.setattr(defaults_module.subprocess, "run", fake_run)

    assert defaults_module._probe_node_version() is None


def test_probe_build_tools_version_accepts_recognized_msvc_banner_on_non_zero_exit(
    monkeypatch: pytest.MonkeyPatch,
):
    availability = {
        "cl": "C:\\BuildTools\\cl.exe",
        "gcc": None,
        "clang": None,
        "cmake": "C:\\Tools\\cmake.exe",
        "nmake": None,
        "make": None,
    }
    msvc_banner = "Microsoft (R) C/C++ Optimizing Compiler Version 19.39.33523 for x64"

    def fake_run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        if tuple(command) == ("cl",):
            return subprocess.CompletedProcess(
                command,
                2,
                stdout="",
                stderr=f"{msvc_banner}\nusage: cl [ option... ] filename... [ /link linkoption... ]\n",
            )
        if tuple(command) == ("cmake", "--version"):
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="cmake version 3.31.6\n",
                stderr="",
            )
        raise AssertionError(f"Unexpected command: {command!r}")

    monkeypatch.setattr(defaults_module.shutil, "which", lambda name: availability.get(name))
    monkeypatch.setattr(defaults_module.subprocess, "run", fake_run)

    assert (
        defaults_module._probe_build_tools_version()
        == "Microsoft (R) C/C++ Optimizing Compiler Version 19.39.33523 for x64; cmake version 3.31.6"
    )


def test_run_installer_uses_real_default_scan_apply_and_write_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    def fake_collect_installer_answers(session: InstallerSession):
        session.install_root = str(tmp_path / "install-root")
        return session

    monkeypatch.setattr(defaults_module, "collect_installer_answers", fake_collect_installer_answers)
    monkeypatch.setattr(defaults_module, "_default_temp_root", lambda: tmp_path / "temp-runs")
    availability = {
        "git": "C:\\Tools\\git.exe",
        "node": "C:\\Tools\\node.exe",
        "npm": "C:\\Tools\\npm.cmd",
        "gcc": "C:\\Tools\\gcc.exe",
        "cmake": "C:\\Tools\\cmake.exe",
    }
    banners = {
        ("git", "--version"): "git version 2.49.0.windows.1",
        ("node", "--version"): "v22.14.0",
        ("npm", "--version"): "10.9.2",
        ("gcc", "--version"): "gcc (GCC) 14.2.0",
        ("cmake", "--version"): "cmake version 3.31.6",
    }
    monkeypatch.setattr(defaults_module.shutil, "which", lambda name: availability.get(name))
    monkeypatch.setattr(
        defaults_module,
        "_capture_first_available_build_tool_output",
        lambda *commands: next(
            (
                banners.get(tuple(command))
                for command in commands
                if availability.get(command[0]) and banners.get(tuple(command))
            ),
            None,
        ),
    )
    monkeypatch.setattr(
        defaults_module,
        "_capture_first_output_line",
        lambda command: banners.get(tuple(command)),
    )

    result = run_installer()
    run_dir = (
        tmp_path
        / "temp-runs"
        / "LocalAIControlCenterInstaller"
        / "runs"
        / result["started_at"].replace(":", "-")
    )
    temp_report_path = run_dir / "install-report.json"
    install_report_path = tmp_path / "install-root" / "logs" / "install-report.json"
    temp_payload = json.loads(temp_report_path.read_text(encoding="utf-8"))
    install_payload = json.loads(install_report_path.read_text(encoding="utf-8"))

    assert result["bootstrap_status"] == "ready"
    assert result["failing_step"] is None
    assert [dependency["version"] for dependency in result["dependencies"]] == [
        defaults_module.sys.version.split()[0],
        "git version 2.49.0.windows.1",
        "v22.14.0; npm 10.9.2",
        "gcc (GCC) 14.2.0; cmake version 3.31.6",
    ]
    assert all(dependency["status"] == "ready" for dependency in result["dependencies"])
    assert temp_report_path.exists()
    assert install_report_path.exists()
    assert temp_payload["bootstrap_status"] == "ready"
    assert temp_payload["dependencies"][2]["version"] == "v22.14.0; npm 10.9.2"
    assert temp_payload["dependencies"][3]["version"] == "gcc (GCC) 14.2.0; cmake version 3.31.6"
    assert install_payload["bootstrap_status"] == "ready"
