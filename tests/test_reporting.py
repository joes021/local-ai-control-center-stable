import json
from pathlib import Path

from local_ai_control_center_installer.reporting import (
    build_run_paths,
    persist_install_root_reports,
    write_human_log,
    write_json_report,
)
from local_ai_control_center_installer.session import DependencyRecord, InstallerSession


def test_build_run_paths_keeps_temp_artifacts_even_for_failed_runs(tmp_path: Path):
    paths = build_run_paths(tmp_path, "2026-05-20T10-00-00")
    expected_run_dir = (
        tmp_path / "LocalAIControlCenterInstaller" / "runs" / "2026-05-20T10-00-00"
    )
    assert paths.run_dir == expected_run_dir
    assert paths.log_path == expected_run_dir / "install.log"
    assert paths.json_report_path == expected_run_dir / "install-report.json"


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
    assert "Runtime payload status: skipped" in contents
    assert "Runtime artifact status: skipped" in contents
    assert "Starter model status: skipped" in contents
    assert "Active model config status: skipped" in contents
    assert "Pinned runtime artifact id: None" in contents
    assert "Selected starter model: None" in contents
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
        runtime_payload_status="failed",
        runtime_artifact_status="failed",
        starter_model_status="skipped",
        active_model_config_status="skipped",
        runtime_artifact_id="runtime-win-x64",
        starter_model="qwen2.5-7b-instruct",
        runtime_artifact_path=str(tmp_path / "install-root" / "runtime"),
        starter_model_path=str(tmp_path / "install-root" / "models" / "starter.gguf"),
        active_model_config_path=str(tmp_path / "install-root" / "config" / "active-model.json"),
        runtime_metadata_path=str(tmp_path / "install-root" / "runtime" / "runtime-artifact.json"),
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
    assert payload["runtime_payload_status"] == "failed"
    assert payload["runtime_artifact_status"] == "failed"
    assert payload["starter_model_status"] == "skipped"
    assert payload["active_model_config_status"] == "skipped"
    assert payload["runtime_artifact_id"] == "runtime-win-x64"
    assert payload["starter_model"] == "qwen2.5-7b-instruct"
    assert payload["runtime_artifact_path"] == session.runtime_artifact_path
    assert payload["starter_model_path"] == session.starter_model_path
    assert payload["active_model_config_path"] == session.active_model_config_path
    assert payload["runtime_metadata_path"] == session.runtime_metadata_path
    assert payload["dependencies"] == [session.dependencies[0].to_dict()]


def test_persist_install_root_reports_rewrites_log_report_and_session_snapshot(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    log_path = install_root / "logs" / "install.log"
    report_path = install_root / "logs" / "install-report.json"
    session_path = install_root / "config" / "installer-session.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("stale log\n", encoding="utf-8")
    report_path.write_text("{\"stale\": true}\n", encoding="utf-8")
    session_path.write_text("{\"stale\": true}\n", encoding="utf-8")

    session = InstallerSession(
        install_root=str(install_root),
        bootstrap_status="ready",
        runtime_payload_status="ready",
        runtime_artifact_status="ready",
        starter_model_status="ready",
        active_model_config_status="ready",
        runtime_artifact_id="runtime-win-x64",
        starter_model="qwen2.5-7b-instruct",
        runtime_artifact_path=str(install_root / "runtime"),
        starter_model_path=str(install_root / "models" / "starter.gguf"),
        active_model_config_path=str(install_root / "config" / "active-model.json"),
        runtime_metadata_path=str(install_root / "runtime" / "runtime-artifact.json"),
    )

    persist_install_root_reports(session)

    assert "stale" not in log_path.read_text(encoding="utf-8")
    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    session_payload = json.loads(session_path.read_text(encoding="utf-8"))
    assert report_payload["runtime_payload_status"] == "ready"
    assert report_payload["starter_model"] == "qwen2.5-7b-instruct"
    assert session_payload["runtime_artifact_id"] == "runtime-win-x64"
    assert session_payload["active_model_config_path"] == str(
        install_root / "config" / "active-model.json"
    )
