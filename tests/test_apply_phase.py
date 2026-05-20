from pathlib import Path

from local_ai_control_center_installer.apply_phase import apply_bootstrap_phase
from local_ai_control_center_installer.reporting import build_run_paths
from local_ai_control_center_installer.session import DependencyRecord, InstallerSession


def test_apply_bootstrap_phase_marks_ready_only_when_all_required_dependencies_are_ready(
    tmp_path: Path,
):
    session = InstallerSession(
        install_root=str(tmp_path / "install-root"),
        dependencies=[
            DependencyRecord(name="python", required=True, status="ready", detected=True),
            DependencyRecord(name="git", required=True, status="ready", detected=True),
        ],
    )

    updated = apply_bootstrap_phase(session, temp_root=tmp_path / "temp-runs")

    assert updated.bootstrap_status == "ready"
    assert Path(updated.install_root, "config", "installer-session.json").exists()
    assert Path(updated.install_root, "logs", "install-report.json").exists()


def test_apply_bootstrap_phase_marks_blocked_dependency_runs_as_failed_and_persists_temp_artifacts(
    tmp_path: Path,
):
    session = InstallerSession(
        started_at="2026-05-20T10:00:00",
        install_root=str(tmp_path / "install-root"),
        dependencies=[
            DependencyRecord(name="python", required=True, status="ready", detected=True),
            DependencyRecord(
                name="node",
                required=True,
                status="failed-install",
                detected=False,
            ),
        ],
    )

    updated = apply_bootstrap_phase(session, temp_root=tmp_path / "temp-runs")
    run_paths = build_run_paths(tmp_path / "temp-runs", "2026-05-20T10-00-00")

    assert updated.bootstrap_status == "failed"
    assert updated.failing_step == "dependency-bootstrap"
    assert updated.product_installation_status == "incomplete"
    assert Path(updated.install_root, "logs").is_dir()
    assert run_paths.log_path.exists()
    assert run_paths.json_report_path.exists()
