import re
import time

import pytest

import local_ai_control_center_installer.defaults as defaults_module
from local_ai_control_center_installer.download_plan import DownloadPlan
from local_ai_control_center_installer.session import InstallerSession


def test_default_scan_dependencies_tracks_only_runtime_prerequisites_for_prebuilt_installer(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    session = InstallerSession()
    install_calls: list[str] = []

    monkeypatch.setattr(defaults_module, "_probe_python_version", lambda: "3.13.7")
    monkeypatch.setattr(defaults_module, "_probe_git_version", lambda: None)
    monkeypatch.setattr(defaults_module, "_probe_node_version", lambda: None)
    monkeypatch.setattr(
        defaults_module,
        "_probe_build_tools_version",
        lambda: None,
    )
    monkeypatch.setattr(
        defaults_module,
        "_build_dependency_install_strategies",
        lambda platform=None: {
            "git": lambda: install_calls.append("git") or True,
            "node": lambda: install_calls.append("node") or True,
            "build-tools": lambda: install_calls.append("build-tools") or True,
        },
    )

    updated = defaults_module.default_scan_dependencies(session)
    captured = capsys.readouterr()

    assert updated is session
    assert install_calls == []
    assert [record.name for record in updated.dependencies] == ["python"]
    assert [record.status for record in updated.dependencies] == ["ready"]
    assert [record.version for record in updated.dependencies] == ["3.13.7"]
    assert "Dependency ready: python (3.13.7)" in captured.out
    assert "Missing dependency detected:" not in captured.out


def test_build_dependency_install_strategies_is_empty_on_linux():
    assert defaults_module._build_dependency_install_strategies("linux") == {}


def test_default_scan_dependencies_surfaces_failed_python_runtime_detection(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    session = InstallerSession()

    monkeypatch.setattr(defaults_module, "_probe_python_version", lambda: None)
    monkeypatch.setattr(defaults_module, "_probe_git_version", lambda: None)
    monkeypatch.setattr(defaults_module, "_probe_node_version", lambda: None)
    monkeypatch.setattr(
        defaults_module,
        "_probe_build_tools_version",
        lambda: None,
    )
    monkeypatch.setattr(
        defaults_module,
        "_build_dependency_install_strategies",
        lambda platform=None: {},
    )

    updated = defaults_module.default_scan_dependencies(session)
    captured = capsys.readouterr()

    python_record = next(record for record in updated.dependencies if record.name == "python")
    assert python_record.status == "failed-install"
    assert python_record.install_attempted is True
    assert python_record.install_succeeded is False
    assert "Automatic install failed: python (no packaged strategy)" in captured.out


def test_default_phase_wrappers_print_progress_for_reused_runtime_and_verification_steps(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    session = InstallerSession(
        bootstrap_status="ready",
        install_opencode=True,
        attempt_turboquant=True,
    )

    monkeypatch.setattr(
        defaults_module,
        "build_download_plan",
        lambda current_session: DownloadPlan(items=()),
    )
    monkeypatch.setattr(
        defaults_module,
        "apply_bootstrap_phase",
        lambda current_session, **_: _mark_bootstrap_ready(current_session),
    )
    monkeypatch.setattr(
        defaults_module,
        "apply_runtime_payload",
        lambda current_session, **_: _mark_runtime_payload_ready(current_session),
    )
    monkeypatch.setattr(
        defaults_module,
        "apply_server_verification",
        lambda current_session, **_: _mark_server_verification_ready(current_session),
    )
    monkeypatch.setattr(
        defaults_module,
        "apply_opencode_bootstrap",
        lambda current_session, **_: _mark_opencode_artifact_ready(current_session),
    )
    monkeypatch.setattr(
        defaults_module,
        "apply_opencode_verification",
        lambda current_session, **_: _mark_opencode_verification_ready(current_session),
    )
    monkeypatch.setattr(
        defaults_module,
        "apply_turboquant",
        lambda current_session: _mark_turboquant_failed(current_session),
    )
    monkeypatch.setattr(
        defaults_module,
        "apply_first_run_validation",
        lambda current_session, **_: _mark_first_run_ready(current_session),
    )
    monkeypatch.setattr(
        defaults_module,
        "apply_control_center_integration",
        lambda current_session, **_: _mark_control_center_ready(current_session),
    )
    monkeypatch.setattr(
        defaults_module,
        "apply_product_gate",
        lambda current_session: _mark_product_complete(current_session),
    )
    current_time = {"value": 100.0}

    def fake_monotonic():
        value = current_time["value"]
        current_time["value"] += 4.0
        return value

    monkeypatch.setattr(defaults_module.time, "monotonic", fake_monotonic)

    defaults_module.default_scan_dependencies(session)
    defaults_module.default_apply_phase(session)
    defaults_module.default_prepare_download_plan(session)
    defaults_module.default_apply_runtime_payload(session)
    defaults_module.default_apply_server_verification(session)
    defaults_module.default_apply_opencode_bootstrap(session)
    defaults_module.default_apply_opencode_verification(session)
    defaults_module.default_apply_turboquant(session)
    defaults_module.default_apply_first_run_validation(session)
    defaults_module.default_apply_control_center_integration(session)
    defaults_module.default_apply_product_gate(session)
    captured = capsys.readouterr()

    expected_lines = [
        "Checking installation prerequisites...",
        "Applying bootstrap decisions...",
        "Preparing download plan...",
        "Download plan ready: 0 item(s).",
        "Checking local runtime payload...",
        "Runtime payload status: ready",
        "Verifying local llama.cpp server...",
        "llama.cpp server verification status: ready",
        "Checking OpenCode artifact...",
        "OpenCode artifact status: ready",
        "Verifying OpenCode live route...",
        "OpenCode live-route verification status: ready",
        "Checking TurboQuant...",
        "TurboQuant status: failed",
        "Running first-run OpenCode smoke...",
        "First-run smoke status: ready",
        "Deploying and launching control panel...",
        "Control panel launch status: ready",
        "Finalizing installation status...",
        "Product installation status: complete",
    ]
    for line in expected_lines:
        assert re.search(
            r"\[\d+/11 \| elapsed [0-9:]+ \| ETA (?:--:--|[0-9:]+)\] "
            + re.escape(line),
            captured.out,
        )


def test_run_phase_with_status_emits_heartbeat_for_silent_long_running_step(
    capsys: pytest.CaptureFixture[str],
):
    session = InstallerSession()
    defaults_module._reset_install_progress_tracker()

    def slow_step(current_session: InstallerSession) -> InstallerSession:
        time.sleep(0.08)
        current_session.first_run_status = "ready"
        return current_session

    defaults_module._run_phase_with_status(
        session,
        step_index=9,
        start_message="Running first-run OpenCode smoke...",
        status_label="First-run smoke status",
        heartbeat_message="First-run OpenCode smoke is still running...",
        expected_duration_seconds=0.2,
        heartbeat_interval_seconds=0.02,
        step_fn=slow_step,
        status_getter=lambda current_session: current_session.first_run_status,
    )
    captured = capsys.readouterr()

    assert "First-run OpenCode smoke is still running..." in captured.out


def test_format_phase_prefix_uses_timeout_bound_eta_for_active_step(
    monkeypatch: pytest.MonkeyPatch,
):
    tracker = defaults_module.InstallProgressTracker(
        start_monotonic=0.0,
        completed_durations=[10.0] * 8,
        active_step_index=9,
        active_step_started_at=100.0,
        active_step_expected_duration=300.0,
        last_output_monotonic=100.0,
    )

    monkeypatch.setattr(defaults_module.time, "monotonic", lambda: 220.0)

    prefix = defaults_module._format_phase_prefix_for_tracker(
        tracker,
        9,
        complete=False,
    )

    assert "elapsed 03:40" in prefix
    assert "ETA 03:20" in prefix


def _mark_runtime_payload_ready(session: InstallerSession) -> InstallerSession:
    session.runtime_payload_status = "ready"
    return session


def _mark_bootstrap_ready(session: InstallerSession) -> InstallerSession:
    session.bootstrap_status = "ready"
    return session


def _mark_server_verification_ready(session: InstallerSession) -> InstallerSession:
    session.server_verification_status = "ready"
    return session


def _mark_opencode_artifact_ready(session: InstallerSession) -> InstallerSession:
    session.opencode_artifact_status = "ready"
    return session


def _mark_opencode_verification_ready(session: InstallerSession) -> InstallerSession:
    session.opencode_verification_status = "ready"
    return session


def _mark_turboquant_failed(session: InstallerSession) -> InstallerSession:
    session.turboquant_status = "failed"
    return session


def _mark_first_run_ready(session: InstallerSession) -> InstallerSession:
    session.first_run_status = "ready"
    return session


def _mark_control_center_ready(session: InstallerSession) -> InstallerSession:
    session.control_center_runtime_status = "ready"
    session.control_center_launch_status = "ready"
    return session


def _mark_product_complete(session: InstallerSession) -> InstallerSession:
    session.product_installation_status = "complete"
    return session
