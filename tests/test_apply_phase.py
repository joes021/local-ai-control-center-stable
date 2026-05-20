import json
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


def test_apply_bootstrap_phase_writes_temp_run_artifacts_before_install_root_persistence_on_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setattr(apply_phase_module, "_generate_fallback_run_id", lambda: "run-order")
    run_paths = build_run_paths(tmp_path / "temp-runs", "run-order")
    install_root = tmp_path / "install-root"
    install_log_path = install_root / "logs" / "install.log"
    install_report_path = install_root / "logs" / "install-report.json"
    install_session_path = install_root / "config" / "installer-session.json"
    events: list[tuple[str, str, str | None]] = []

    def record_log(session: InstallerSession, log_path: Path) -> Path:
        if log_path == run_paths.log_path:
            events.append(("temp-log", session.bootstrap_status, session.failing_step))
        elif log_path == install_log_path:
            events.append(("install-log", session.bootstrap_status, session.failing_step))
        return log_path

    def record_report(session: InstallerSession, report_path: Path) -> Path:
        if report_path == run_paths.json_report_path:
            events.append(("temp-json", session.bootstrap_status, session.failing_step))
        elif report_path == install_report_path:
            events.append(("install-json", session.bootstrap_status, session.failing_step))
        return report_path

    def record_snapshot(session: InstallerSession, session_path: Path) -> Path:
        if session_path == install_session_path:
            events.append(("install-session", session.bootstrap_status, session.failing_step))
        return session_path

    monkeypatch.setattr(apply_phase_module, "write_human_log", record_log)
    monkeypatch.setattr(apply_phase_module, "write_json_report", record_report)
    monkeypatch.setattr(apply_phase_module, "write_session_snapshot", record_snapshot)

    session = InstallerSession(
        install_root=str(install_root),
        dependencies=[
            DependencyRecord(name="python", required=True, status="ready", detected=True),
            DependencyRecord(name="git", required=True, status="ready", detected=True),
        ],
    )

    updated = apply_bootstrap_phase(session, temp_root=tmp_path / "temp-runs")

    assert updated.bootstrap_status == "ready"
    assert events == [
        ("temp-log", "ready", None),
        ("temp-json", "ready", None),
        ("install-log", "ready", None),
        ("install-json", "ready", None),
        ("install-session", "ready", None),
    ]


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


def test_apply_bootstrap_phase_marks_install_root_persistence_failure_in_temp_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setattr(
        apply_phase_module,
        "_generate_fallback_run_id",
        lambda: "run-persistence-failure",
    )
    install_root = tmp_path / "install-root"
    original_write_human_log = apply_phase_module.write_human_log

    def fail_on_install_root_log(session: InstallerSession, log_path: Path) -> Path:
        if log_path == install_root / "logs" / "install.log":
            raise OSError("disk full")
        return original_write_human_log(session, log_path)

    monkeypatch.setattr(apply_phase_module, "write_human_log", fail_on_install_root_log)

    session = InstallerSession(
        install_root=str(install_root),
        dependencies=[
            DependencyRecord(name="python", required=True, status="ready", detected=True),
            DependencyRecord(name="git", required=True, status="ready", detected=True),
        ],
    )

    updated = apply_bootstrap_phase(session, temp_root=tmp_path / "temp-runs")
    run_paths = build_run_paths(tmp_path / "temp-runs", "run-persistence-failure")
    report_payload = json.loads(run_paths.json_report_path.read_text(encoding="utf-8"))
    log_contents = run_paths.log_path.read_text(encoding="utf-8")

    assert updated.bootstrap_status == "failed"
    assert updated.failing_step == "install-root-persistence"
    assert updated.product_installation_status == "incomplete"
    assert report_payload["bootstrap_status"] == "failed"
    assert report_payload["failing_step"] == "install-root-persistence"
    assert "Bootstrap status: failed" in log_contents
    assert "Failing step: install-root-persistence" in log_contents


def test_apply_bootstrap_phase_cleans_partial_install_root_artifacts_on_report_write_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setattr(
        apply_phase_module,
        "_generate_fallback_run_id",
        lambda: "run-cleanup-failure",
    )
    install_root = tmp_path / "install-root"
    original_write_json_report = apply_phase_module.write_json_report

    def fail_on_install_root_report(
        session: InstallerSession,
        report_path: Path,
    ) -> Path:
        if report_path == install_root / "logs" / "install-report.json":
            raise OSError("report write failed")
        return original_write_json_report(session, report_path)

    monkeypatch.setattr(
        apply_phase_module,
        "write_json_report",
        fail_on_install_root_report,
    )

    session = InstallerSession(
        install_root=str(install_root),
        dependencies=[
            DependencyRecord(name="python", required=True, status="ready", detected=True),
            DependencyRecord(name="git", required=True, status="ready", detected=True),
        ],
    )

    updated = apply_bootstrap_phase(session, temp_root=tmp_path / "temp-runs")
    run_paths = build_run_paths(tmp_path / "temp-runs", "run-cleanup-failure")
    report_payload = json.loads(run_paths.json_report_path.read_text(encoding="utf-8"))

    assert updated.bootstrap_status == "failed"
    assert updated.failing_step == "install-root-persistence"
    assert not Path(updated.install_root, "logs", "install.log").exists()
    assert not Path(updated.install_root, "logs", "install-report.json").exists()
    assert not Path(updated.install_root, "config", "installer-session.json").exists()
    assert report_payload["bootstrap_status"] == "failed"
    assert report_payload["failing_step"] == "install-root-persistence"


def test_apply_bootstrap_phase_rolls_back_directories_when_install_root_mkdir_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setattr(
        apply_phase_module,
        "_generate_fallback_run_id",
        lambda: "run-mkdir-failure",
    )
    install_root = tmp_path / "install-root"
    config_dir = install_root / "config"
    original_mkdir = Path.mkdir

    def fail_on_config_dir_mkdir(
        self: Path,
        mode: int = 0o777,
        parents: bool = False,
        exist_ok: bool = False,
    ) -> None:
        if self == config_dir:
            raise OSError("config mkdir failed")
        return original_mkdir(self, mode=mode, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(Path, "mkdir", fail_on_config_dir_mkdir)

    session = InstallerSession(
        install_root=str(install_root),
        dependencies=[
            DependencyRecord(name="python", required=True, status="ready", detected=True),
            DependencyRecord(name="git", required=True, status="ready", detected=True),
        ],
    )

    updated = apply_bootstrap_phase(session, temp_root=tmp_path / "temp-runs")
    run_paths = build_run_paths(tmp_path / "temp-runs", "run-mkdir-failure")
    report_payload = json.loads(run_paths.json_report_path.read_text(encoding="utf-8"))
    log_contents = run_paths.log_path.read_text(encoding="utf-8")

    assert updated.bootstrap_status == "failed"
    assert updated.failing_step == "install-root-persistence"
    assert updated.product_installation_status == "incomplete"
    assert report_payload["bootstrap_status"] == "failed"
    assert report_payload["failing_step"] == "install-root-persistence"
    assert "Bootstrap status: failed" in log_contents
    assert "Failing step: install-root-persistence" in log_contents
    assert not install_root.exists()
