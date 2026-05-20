from pathlib import Path

import pytest

import local_ai_control_center_installer.apply_phase as apply_phase_module
from local_ai_control_center_installer.apply_phase import apply_bootstrap_phase
from local_ai_control_center_installer.reporting import build_run_paths
from local_ai_control_center_installer.session import DependencyRecord, InstallerSession


def test_apply_bootstrap_phase_marks_ready_only_when_all_required_dependencies_are_ready(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setattr(apply_phase_module, "_generate_fallback_run_id", lambda: "run-1")
    session = InstallerSession(
        install_root=f"  {tmp_path / 'install-root'}  ",
        dependencies=[
            DependencyRecord(name="python", required=True, status="ready", detected=True),
            DependencyRecord(name="git", required=True, status="ready", detected=True),
        ],
    )

    updated = apply_bootstrap_phase(session, temp_root=tmp_path / "temp-runs")
    run_paths = build_run_paths(tmp_path / "temp-runs", "run-1")

    assert updated.bootstrap_status == "ready"
    assert updated.product_installation_status == "incomplete"
    assert updated.install_root == str(tmp_path / "install-root")
    assert Path(updated.install_root, "config", "installer-session.json").exists()
    assert Path(updated.install_root, "logs", "install.log").exists()
    assert Path(updated.install_root, "logs", "install-report.json").exists()
    assert run_paths.log_path.exists()
    assert run_paths.json_report_path.exists()


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
    assert run_paths.log_path.exists()
    assert run_paths.json_report_path.exists()
    assert not Path(updated.install_root, "logs", "install.log").exists()
    assert not Path(updated.install_root, "logs", "install-report.json").exists()
    assert not Path(updated.install_root, "config", "installer-session.json").exists()


def test_apply_bootstrap_phase_requires_install_root_before_writing_files(
    tmp_path: Path,
):
    session = InstallerSession(
        install_root="",
        dependencies=[
            DependencyRecord(name="python", required=True, status="ready", detected=True),
        ],
    )

    with pytest.raises(ValueError, match="install_root"):
        apply_bootstrap_phase(session, temp_root=tmp_path / "temp-runs")


def test_apply_bootstrap_phase_uses_unique_fallback_run_ids_without_started_at(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    fallback_run_ids = iter(["run-a", "run-b"])
    monkeypatch.setattr(
        apply_phase_module,
        "_generate_fallback_run_id",
        lambda: next(fallback_run_ids),
    )

    first_session = InstallerSession(
        install_root=str(tmp_path / "install-root-1"),
        dependencies=[
            DependencyRecord(name="python", required=True, status="ready", detected=True),
        ],
    )
    second_session = InstallerSession(
        install_root=str(tmp_path / "install-root-2"),
        dependencies=[
            DependencyRecord(name="python", required=True, status="ready", detected=True),
        ],
    )

    apply_bootstrap_phase(first_session, temp_root=tmp_path / "temp-runs")
    apply_bootstrap_phase(second_session, temp_root=tmp_path / "temp-runs")

    first_run_paths = build_run_paths(tmp_path / "temp-runs", "run-a")
    second_run_paths = build_run_paths(tmp_path / "temp-runs", "run-b")

    assert first_run_paths.run_dir != second_run_paths.run_dir
    assert first_run_paths.log_path.exists()
    assert second_run_paths.log_path.exists()
