import json
from pathlib import Path

from local_ai_control_center_installer.reporting import (
    build_run_paths,
    write_human_log,
    write_json_report,
)
from local_ai_control_center_installer.session import DependencyRecord, InstallerSession


def test_build_run_paths_keeps_temp_artifacts_even_for_failed_runs(tmp_path: Path):
    paths = build_run_paths(tmp_path, "2026-05-20T10-00-00")
    assert str(paths.log_path).endswith("install.log")
    assert "LocalAIControlCenterInstaller" in str(paths.log_path)


def test_write_human_log_includes_install_root_dependency_outcomes_and_failing_step(
    tmp_path: Path,
):
    paths = build_run_paths(tmp_path, "2026-05-20T10-00-00")
    session = InstallerSession(
        install_root=str(tmp_path / "install-root"),
        failing_step="dependency-bootstrap",
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

    write_human_log(session, paths.log_path)

    contents = paths.log_path.read_text(encoding="utf-8")
    assert session.install_root in contents
    assert "python: ready" in contents
    assert "node: failed-install" in contents
    assert "dependency-bootstrap" in contents


def test_write_json_report_serializes_bootstrap_summary(tmp_path: Path):
    paths = build_run_paths(tmp_path, "2026-05-20T10-00-00")
    session = InstallerSession(
        bootstrap_status="failed",
        product_installation_status="incomplete",
        failing_step="dependency-bootstrap",
        install_root=str(tmp_path / "install-root"),
        dependencies=[
            DependencyRecord(name="python", required=True, status="ready", detected=True),
        ],
    )

    write_json_report(session, paths.json_report_path)

    payload = json.loads(paths.json_report_path.read_text(encoding="utf-8"))
    assert payload["bootstrap_status"] == "failed"
    assert payload["product_installation_status"] == "incomplete"
    assert payload["failing_step"] == "dependency-bootstrap"
    assert payload["install_root"] == session.install_root
    assert payload["dependencies"] == [session.dependencies[0].to_dict()]
