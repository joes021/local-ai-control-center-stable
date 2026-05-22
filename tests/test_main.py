import json
import subprocess

import pytest

import local_ai_control_center_installer.defaults as defaults_module
import local_ai_control_center_installer.main as main_module
import local_ai_control_center_installer.prompts as prompts_module
from local_ai_control_center_installer.download_plan import DownloadPlan, DownloadPlanItem
from local_ai_control_center_installer.main import run_installer
from local_ai_control_center_installer.prompts import (
    PromptCancelledError,
    StarterModelCatalogError,
)
from local_ai_control_center_installer.session import InstallerSession

TEST_MARKER = "LACC_VERIFY_MARKER:test-marker"
TEST_VERIFIED_OPENCODE_COMMAND = (
    "opencode --pure run --format json --model "
    f'local-lacc/recommended-6gb "Repeat this exact token once: {TEST_MARKER}"'
)


def test_main_delegates_to_run_installer_and_returns_zero(monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []

    def fake_run_installer():
        calls.append("run")
        return {
            "bootstrap_status": "ready",
            "runtime_payload_status": "ready",
            "server_verification_status": "ready",
            "opencode_verification_status": "ready",
        }

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


def test_main_returns_non_zero_when_starter_model_catalog_setup_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    def fake_run_installer():
        raise StarterModelCatalogError("Starter model catalog is unavailable.")

    monkeypatch.setattr(main_module, "run_installer", fake_run_installer)

    assert main_module.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Starter model catalog is unavailable.\n"
    assert "Traceback" not in captured.err


@pytest.mark.parametrize(
    ("side_effect", "expected_message"),
    [
        (FileNotFoundError("missing runtime manifest"), "missing runtime manifest"),
        (ValueError("malformed runtime manifest"), "malformed runtime manifest"),
        (
            ValueError("Duplicate starter model prompt_order: 1"),
            "Duplicate starter model prompt_order: 1",
        ),
    ],
)
def test_main_exits_cleanly_when_prompt_path_cannot_load_starter_model_catalog(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    side_effect,
    expected_message,
):
    def raise_catalog_error():
        raise side_effect

    monkeypatch.setattr(prompts_module, "load_runtime_manifest", raise_catalog_error)
    monkeypatch.setattr(
        defaults_module,
        "collect_installer_answers",
        lambda session: prompts_module.collect_installer_answers(
            session,
            input_fn=lambda _: "",
        ),
    )

    assert main_module.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert expected_message in captured.err
    assert "Traceback" not in captured.err


def test_main_returns_non_zero_when_bootstrap_status_is_failed(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_run_installer():
        return {"bootstrap_status": "failed", "runtime_payload_status": "skipped"}

    monkeypatch.setattr(main_module, "run_installer", fake_run_installer)

    assert main_module.main() == 1


def test_main_returns_non_zero_when_runtime_payload_status_is_failed(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_run_installer():
        return {"bootstrap_status": "ready", "runtime_payload_status": "failed"}

    monkeypatch.setattr(main_module, "run_installer", fake_run_installer)

    assert main_module.main() == 1


def test_main_returns_non_zero_when_server_verification_status_is_failed(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_run_installer():
        return {
            "bootstrap_status": "ready",
            "runtime_payload_status": "ready",
            "server_verification_status": "failed",
        }

    monkeypatch.setattr(main_module, "run_installer", fake_run_installer)

    assert main_module.main() == 1


def test_main_returns_zero_when_opencode_was_explicitly_skipped(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_run_installer():
        return {
            "bootstrap_status": "ready",
            "runtime_payload_status": "ready",
            "server_verification_status": "ready",
            "install_opencode": False,
            "opencode_artifact_status": "skipped",
            "opencode_verification_status": "skipped",
            "opencode_process_status": "skipped",
            "opencode_connection_status": "skipped",
        }

    monkeypatch.setattr(main_module, "run_installer", fake_run_installer)

    assert main_module.main() == 0


def test_main_returns_zero_when_opencode_was_requested_and_verified(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_run_installer():
        return {
            "bootstrap_status": "ready",
            "runtime_payload_status": "ready",
            "server_verification_status": "ready",
            "install_opencode": True,
            "opencode_verification_status": "ready",
        }

    monkeypatch.setattr(main_module, "run_installer", fake_run_installer)

    assert main_module.main() == 0


def test_main_returns_non_zero_when_opencode_verification_status_is_failed(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_run_installer():
        return {
            "bootstrap_status": "ready",
            "runtime_payload_status": "ready",
            "server_verification_status": "ready",
            "install_opencode": True,
            "opencode_verification_status": "failed",
        }

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
        apply_runtime_payload=lambda session: session,
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
            apply_runtime_payload=lambda session: session,
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
        apply_runtime_payload=lambda session: events.append("runtime") or session,
        write_reports=fake_write_reports,
    )

    assert events == ["collect", "scan", "apply", "runtime", "report"]
    assert written_payloads == [
        {
            "bootstrap_status": "failed",
            "product_installation_status": "incomplete",
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
            "install_opencode": False,
            "attempt_turboquant": False,
            "additional_model_paths": [],
            "download_plan": None,
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
        apply_runtime_payload=lambda session, **_: session,
        write_reports=lambda session, **_: None,
    )

    assert result["bootstrap_status"] == "failed"
    assert result["failing_step"] == "dependency-bootstrap"


def test_run_installer_calls_runtime_collaborator_after_bootstrap_and_before_reporting():
    events: list[str] = []

    def fake_collect(session: InstallerSession, **_):
        events.append("collect")
        return session

    def fake_scan(session: InstallerSession, **_):
        events.append("scan")
        return session

    def fake_apply(session: InstallerSession, **_):
        events.append("apply")
        session.bootstrap_status = "ready"
        return session

    def fake_runtime(session: InstallerSession, **_):
        events.append("runtime")
        session.runtime_payload_status = "ready"
        return session

    def fake_write_reports(session: InstallerSession, **_):
        events.append("report")

    run_installer(
        collect_answers=fake_collect,
        scan_dependencies=fake_scan,
        apply_phase=fake_apply,
        prepare_download_plan=lambda session: events.append("plan") or session,
        apply_runtime_payload=fake_runtime,
        write_reports=fake_write_reports,
    )

    assert events == ["collect", "scan", "apply", "plan", "runtime", "report"]


def test_run_installer_calls_server_verification_after_runtime_and_before_reporting():
    events: list[str] = []

    def fake_apply(session: InstallerSession, **_):
        events.append("bootstrap")
        session.bootstrap_status = "ready"
        return session

    def fake_runtime(session: InstallerSession, **_):
        events.append("runtime")
        session.runtime_payload_status = "ready"
        return session

    def fake_server_verification(session: InstallerSession, **_):
        events.append("server")
        session.server_verification_status = "ready"
        return session

    def fake_write_reports(session: InstallerSession, **_):
        events.append("report")

    run_installer(
        collect_answers=lambda session, **_: session,
        scan_dependencies=lambda session, **_: session,
        apply_phase=fake_apply,
        prepare_download_plan=lambda session: events.append("plan") or session,
        apply_runtime_payload=fake_runtime,
        apply_server_verification=fake_server_verification,
        write_reports=fake_write_reports,
    )

    assert events == ["bootstrap", "plan", "runtime", "server", "report"]


def test_run_installer_calls_opencode_steps_after_server_and_before_reporting():
    events: list[str] = []

    def fake_bootstrap(session: InstallerSession, **_):
        events.append("bootstrap")
        session.bootstrap_status = "ready"
        return session

    def fake_runtime(session: InstallerSession, **_):
        events.append("runtime")
        session.runtime_payload_status = "ready"
        return session

    def fake_server_verification(session: InstallerSession, **_):
        events.append("server")
        session.server_verification_status = "ready"
        return session

    def fake_opencode_bootstrap(session: InstallerSession, **_):
        events.append("opencode-bootstrap")
        session.opencode_artifact_status = "ready"
        return session

    def fake_opencode_verification(session: InstallerSession, **_):
        events.append("opencode-verification")
        session.opencode_verification_status = "ready"
        return session

    def fake_write_reports(session: InstallerSession, **_):
        events.append("report")

    run_installer(
        collect_answers=lambda session, **_: session,
        scan_dependencies=lambda session, **_: session,
        apply_phase=fake_bootstrap,
        prepare_download_plan=lambda session: events.append("plan") or session,
        apply_runtime_payload=fake_runtime,
        apply_server_verification=fake_server_verification,
        apply_opencode_bootstrap=fake_opencode_bootstrap,
        apply_opencode_verification=fake_opencode_verification,
        write_reports=fake_write_reports,
    )

    assert events == [
        "bootstrap",
        "plan",
        "runtime",
        "server",
        "opencode-bootstrap",
        "opencode-verification",
        "report",
    ]


def test_default_prepare_download_plan_builds_and_persists_single_queue_truth(
    monkeypatch: pytest.MonkeyPatch,
):
    session = InstallerSession(
        bootstrap_status="ready",
        install_root="C:\\install-root",
        starter_model="recommended-12gb",
    )
    planned_items = DownloadPlan(
        items=(
            DownloadPlanItem(
                key="runtime-artifact",
                label="llama.cpp runtime",
                url="https://example.invalid/runtime.zip",
                destination_hint="runtime/llama.cpp",
                size_bytes=None,
                queue_index=1,
                queue_total=2,
            ),
            DownloadPlanItem(
                key="starter-model:recommended-12gb",
                label="starter model recommended-12gb",
                url="https://example.invalid/model.gguf",
                destination_hint="models/recommended-12gb/recommended-12gb.gguf",
                size_bytes=123,
                queue_index=2,
                queue_total=2,
            ),
        )
    )
    calls = {"count": 0}

    def fake_build_download_plan(current_session: InstallerSession) -> DownloadPlan:
        calls["count"] += 1
        assert current_session is session
        return planned_items

    monkeypatch.setattr(defaults_module, "build_download_plan", fake_build_download_plan)

    updated = defaults_module.default_prepare_download_plan(session)
    second_pass = defaults_module.default_prepare_download_plan(updated)

    assert updated.download_plan == planned_items
    assert second_pass.download_plan == planned_items
    assert calls["count"] == 1


def test_default_prepare_download_plan_skips_build_when_bootstrap_not_ready(
    monkeypatch: pytest.MonkeyPatch,
):
    session = InstallerSession(
        bootstrap_status="failed",
        install_root="C:\\install-root",
        starter_model="recommended-12gb",
    )

    monkeypatch.setattr(
        defaults_module,
        "build_download_plan",
        lambda current_session: (_ for _ in ()).throw(AssertionError("should not build")),
    )

    updated = defaults_module.default_prepare_download_plan(session)

    assert updated.download_plan is None


def test_run_installer_keeps_product_installation_incomplete_after_opencode_success():
    def fake_bootstrap(session: InstallerSession, **_):
        session.bootstrap_status = "ready"
        return session

    def fake_runtime(session: InstallerSession, **_):
        session.runtime_payload_status = "ready"
        return session

    def fake_server_verification(session: InstallerSession, **_):
        session.server_verification_status = "ready"
        return session

    def fake_opencode_bootstrap(session: InstallerSession, **_):
        session.opencode_artifact_status = "ready"
        return session

    def fake_opencode_verification(session: InstallerSession, **_):
        session.opencode_verification_status = "ready"
        session.opencode_process_status = "ready"
        session.opencode_connection_status = "ready"
        return session

    result = run_installer(
        collect_answers=lambda session, **_: session,
        scan_dependencies=lambda session, **_: session,
        apply_phase=fake_bootstrap,
        apply_runtime_payload=fake_runtime,
        apply_server_verification=fake_server_verification,
        apply_opencode_bootstrap=fake_opencode_bootstrap,
        apply_opencode_verification=fake_opencode_verification,
        write_reports=lambda session, **_: None,
    )

    assert result["product_installation_status"] == "incomplete"
    assert result["opencode_verification_status"] == "ready"


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
    monkeypatch.setattr(
        defaults_module,
        "default_apply_runtime_payload",
        lambda session: _mark_runtime_ready(session, tmp_path),
    )
    monkeypatch.setattr(
        defaults_module,
        "default_apply_server_verification",
        lambda session: _mark_server_verification_ready(session, tmp_path),
    )
    monkeypatch.setattr(
        defaults_module,
        "default_apply_opencode_bootstrap",
        lambda session: _mark_opencode_bootstrap_ready(session, tmp_path),
    )
    monkeypatch.setattr(
        defaults_module,
        "default_apply_opencode_verification",
        lambda session: _mark_opencode_verification_ready(session, tmp_path),
    )
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
    assert temp_payload["runtime_payload_status"] == "ready"
    assert temp_payload["server_verification_status"] == "ready"
    assert temp_payload["opencode_artifact_status"] == "ready"
    assert temp_payload["opencode_verification_status"] == "ready"
    assert temp_payload["dependencies"][2]["version"] == "v22.14.0; npm 10.9.2"
    assert temp_payload["dependencies"][3]["version"] == "gcc (GCC) 14.2.0; cmake version 3.31.6"
    assert install_payload["bootstrap_status"] == "ready"
    assert install_payload["runtime_payload_status"] == "ready"
    assert install_payload["server_verification_status"] == "ready"
    assert install_payload["opencode_artifact_status"] == "ready"
    assert install_payload["opencode_verification_status"] == "ready"


def test_run_installer_real_default_path_converts_install_root_report_persistence_error_to_failed_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    def fake_collect_installer_answers(session: InstallerSession):
        session.install_root = str(tmp_path / "install-root")
        session.starter_model = "qwen2.5-7b-instruct"
        return session

    monkeypatch.setattr(defaults_module, "collect_installer_answers", fake_collect_installer_answers)
    monkeypatch.setattr(defaults_module, "_default_temp_root", lambda: tmp_path / "temp-runs")
    monkeypatch.setattr(
        defaults_module,
        "default_apply_runtime_payload",
        lambda session: _mark_runtime_ready(session, tmp_path),
    )
    monkeypatch.setattr(
        defaults_module,
        "default_apply_server_verification",
        lambda session: _mark_server_verification_ready(session, tmp_path),
    )
    monkeypatch.setattr(
        defaults_module,
        "default_apply_opencode_bootstrap",
        lambda session: _mark_opencode_bootstrap_ready(session, tmp_path),
    )
    monkeypatch.setattr(
        defaults_module,
        "default_apply_opencode_verification",
        lambda session: _mark_opencode_verification_ready(session, tmp_path),
    )
    monkeypatch.setattr(
        defaults_module,
        "persist_install_root_reports",
        lambda session: (_ for _ in ()).throw(OSError("locked")),
    )
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
    temp_payload = json.loads(temp_report_path.read_text(encoding="utf-8"))

    assert result["runtime_payload_status"] == "failed"
    assert result["failing_step"] == "install-root-persistence"
    assert result["error_message"] == "locked"
    assert temp_payload["runtime_payload_status"] == "failed"
    assert temp_payload["failing_step"] == "install-root-persistence"
    assert temp_payload["error_message"] == "locked"


def _mark_runtime_ready(session: InstallerSession, tmp_path) -> InstallerSession:
    install_root = tmp_path / "install-root"
    session.runtime_payload_status = "ready"
    session.runtime_artifact_status = "ready"
    session.starter_model_status = "ready"
    session.active_model_config_status = "ready"
    session.runtime_artifact_id = "runtime-win-x64"
    session.starter_model = "qwen2.5-7b-instruct"
    session.runtime_artifact_path = str(install_root / "runtime")
    session.starter_model_path = str(install_root / "models" / "starter.gguf")
    session.active_model_config_path = str(install_root / "config" / "active-model.json")
    session.runtime_metadata_path = str(install_root / "runtime" / "runtime-artifact.json")
    return session


def _mark_server_verification_ready(
    session: InstallerSession,
    tmp_path,
) -> InstallerSession:
    log_path = (
        tmp_path
        / "temp-runs"
        / "LocalAIControlCenterInstaller"
        / "runs"
        / session.started_at.replace(":", "-")
        / "llama-server.log"
    )
    session.server_verification_status = "ready"
    session.server_process_status = "ready"
    session.server_health_status = "ready"
    session.verified_server_port = 8080
    session.verified_server_url = "http://127.0.0.1:8080"
    session.server_log_path = str(log_path)
    return session


def _mark_opencode_bootstrap_ready(
    session: InstallerSession,
    tmp_path,
) -> InstallerSession:
    install_root = tmp_path / "install-root"
    session.opencode_artifact_status = "ready"
    session.opencode_artifact_id = "opencode-windows-x64"
    session.opencode_artifact_path = str(install_root / "tools" / "opencode")
    session.opencode_metadata_path = str(
        install_root / "tools" / "opencode" / "opencode-artifact.json"
    )
    session.opencode_config_path = str(
        install_root / "config" / "opencode" / "managed-config.json"
    )
    return session


def _mark_opencode_verification_ready(
    session: InstallerSession,
    tmp_path,
) -> InstallerSession:
    log_path = (
        tmp_path
        / "temp-runs"
        / "LocalAIControlCenterInstaller"
        / "runs"
        / session.started_at.replace(":", "-")
        / "opencode-verification.log"
    )
    session.opencode_verification_status = "ready"
    session.opencode_process_status = "ready"
    session.opencode_connection_status = "ready"
    session.verified_opencode_command = TEST_VERIFIED_OPENCODE_COMMAND
    session.opencode_log_path = str(log_path)
    return session
