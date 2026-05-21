import json
from pathlib import Path

import pytest

import local_ai_control_center_installer.reporting as reporting_module
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


def test_build_run_paths_exposes_server_log_path(tmp_path: Path):
    paths = build_run_paths(tmp_path, "2026-05-21T10-00-00")
    assert (
        paths.server_log_path
        == tmp_path
        / "LocalAIControlCenterInstaller"
        / "runs"
        / "2026-05-21T10-00-00"
        / "llama-server.log"
    )


def test_build_run_paths_exposes_opencode_log_path(tmp_path: Path):
    paths = build_run_paths(tmp_path, "2026-05-21T10-00-00")
    assert (
        paths.opencode_log_path
        == tmp_path
        / "LocalAIControlCenterInstaller"
        / "runs"
        / "2026-05-21T10-00-00"
        / "opencode-verification.log"
    )


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


def test_write_human_log_includes_server_verification_lines(tmp_path: Path):
    paths = build_run_paths(tmp_path, "2026-05-21T10-00-00")
    session = InstallerSession(
        server_verification_status="failed",
        server_process_status="ready",
        server_health_status="failed",
        verified_server_port=8080,
        verified_server_url="http://127.0.0.1:8080",
        server_log_path=str(paths.server_log_path),
    )

    write_human_log(session, paths.log_path)

    contents = paths.log_path.read_text(encoding="utf-8")
    assert "Server verification status: failed" in contents
    assert "Server process status: ready" in contents
    assert "Server health status: failed" in contents
    assert "Verified server port: 8080" in contents
    assert "Verified server URL: http://127.0.0.1:8080" in contents
    assert "Server log path:" in contents


def test_write_human_log_includes_opencode_summary_lines(tmp_path: Path):
    paths = build_run_paths(tmp_path, "2026-05-21T10-00-00")
    session = InstallerSession(
        opencode_artifact_status="ready",
        opencode_verification_status="failed",
        opencode_process_status="ready",
        opencode_connection_status="failed",
        opencode_artifact_id="opencode-windows-x64",
        opencode_artifact_path=str(tmp_path / "install-root" / "opencode"),
        opencode_metadata_path=str(tmp_path / "install-root" / "opencode" / "opencode-artifact.json"),
        opencode_config_path=str(tmp_path / "install-root" / "config" / "opencode.json"),
        verified_opencode_command="opencode --pure models local-lacc",
        opencode_log_path=str(paths.opencode_log_path),
    )

    write_human_log(session, paths.log_path)

    contents = paths.log_path.read_text(encoding="utf-8")
    assert "OpenCode artifact status: ready" in contents
    assert "OpenCode verification status: failed" in contents
    assert "OpenCode process status: ready" in contents
    assert "OpenCode connection status: failed" in contents
    assert "OpenCode artifact id: opencode-windows-x64" in contents
    assert "Verified OpenCode command: opencode --pure models local-lacc" in contents
    assert "OpenCode log path:" in contents


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


def test_write_json_report_serializes_server_verification_summary(tmp_path: Path):
    paths = build_run_paths(tmp_path, "2026-05-21T10-00-00")
    session = InstallerSession(
        bootstrap_status="ready",
        runtime_payload_status="ready",
        server_verification_status="failed",
        server_process_status="ready",
        server_health_status="failed",
        verified_server_port=8080,
        verified_server_url="http://127.0.0.1:8080",
        server_log_path=str(paths.server_log_path),
        failing_step="server-health",
        install_root=str(tmp_path / "install-root"),
    )

    write_json_report(session, paths.json_report_path)

    payload = json.loads(paths.json_report_path.read_text(encoding="utf-8"))
    assert payload["server_verification_status"] == "failed"
    assert payload["server_process_status"] == "ready"
    assert payload["server_health_status"] == "failed"
    assert payload["verified_server_port"] == 8080
    assert payload["verified_server_url"] == "http://127.0.0.1:8080"
    assert payload["server_log_path"] == str(paths.server_log_path)


def test_write_json_report_serializes_opencode_summary(tmp_path: Path):
    paths = build_run_paths(tmp_path, "2026-05-21T10-00-00")
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(tmp_path / "install-root"),
        opencode_artifact_status="ready",
        opencode_verification_status="failed",
        opencode_process_status="ready",
        opencode_connection_status="failed",
        opencode_artifact_id="opencode-windows-x64",
        opencode_artifact_path=str(tmp_path / "install-root" / "opencode"),
        opencode_metadata_path=str(tmp_path / "install-root" / "opencode" / "opencode-artifact.json"),
        opencode_config_path=str(tmp_path / "install-root" / "config" / "opencode.json"),
        verified_opencode_command="opencode --pure models local-lacc",
        opencode_log_path=str(paths.opencode_log_path),
    )

    write_json_report(session, paths.json_report_path)

    payload = json.loads(paths.json_report_path.read_text(encoding="utf-8"))
    assert payload["opencode_artifact_status"] == "ready"
    assert payload["opencode_verification_status"] == "failed"
    assert payload["opencode_process_status"] == "ready"
    assert payload["opencode_connection_status"] == "failed"
    assert payload["opencode_artifact_id"] == "opencode-windows-x64"
    assert payload["opencode_artifact_path"] == session.opencode_artifact_path
    assert payload["opencode_metadata_path"] == session.opencode_metadata_path
    assert payload["opencode_config_path"] == session.opencode_config_path
    assert payload["verified_opencode_command"] == "opencode --pure models local-lacc"
    assert payload["opencode_log_path"] == str(paths.opencode_log_path)


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


def test_persist_install_root_reports_copies_opencode_log(tmp_path: Path):
    install_root = tmp_path / "install-root"
    temp_opencode_log = tmp_path / "temp-run" / "opencode-verification.log"
    temp_opencode_log.parent.mkdir(parents=True, exist_ok=True)
    temp_opencode_log.write_text("OpenCode verification output\n", encoding="utf-8")

    session = InstallerSession(
        install_root=str(install_root),
        opencode_log_path=str(temp_opencode_log),
    )

    persist_install_root_reports(session)

    persisted_opencode_log = install_root / "logs" / "opencode-verification.log"
    assert persisted_opencode_log.read_text(encoding="utf-8") == "OpenCode verification output\n"
    assert session.opencode_log_path == str(persisted_opencode_log)

    install_log_contents = (install_root / "logs" / "install.log").read_text(encoding="utf-8")
    report_payload = json.loads((install_root / "logs" / "install-report.json").read_text(encoding="utf-8"))
    session_payload = json.loads((install_root / "config" / "installer-session.json").read_text(encoding="utf-8"))
    assert f"OpenCode log path: {persisted_opencode_log}" in install_log_contents
    assert report_payload["opencode_log_path"] == str(persisted_opencode_log)
    assert session_payload["opencode_log_path"] == str(persisted_opencode_log)


def test_persist_install_root_reports_copies_opencode_log_bytes_verbatim(tmp_path: Path):
    install_root = tmp_path / "install-root"
    temp_opencode_log = tmp_path / "temp-run" / "opencode-verification.log"
    raw_bytes = b"\xff\xfeOpenCode\x00log\r\n\x80\x81"
    temp_opencode_log.parent.mkdir(parents=True, exist_ok=True)
    temp_opencode_log.write_bytes(raw_bytes)

    session = InstallerSession(
        install_root=str(install_root),
        opencode_log_path=str(temp_opencode_log),
    )

    persist_install_root_reports(session)

    persisted_opencode_log = install_root / "logs" / "opencode-verification.log"
    assert persisted_opencode_log.read_bytes() == raw_bytes
    assert session.opencode_log_path == str(persisted_opencode_log)


def test_persist_install_root_reports_restores_temp_opencode_log_path_on_promotion_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    install_root = tmp_path / "install-root"
    temp_opencode_log = tmp_path / "temp-run" / "opencode-verification.log"
    temp_opencode_log.parent.mkdir(parents=True, exist_ok=True)
    temp_opencode_log.write_text("OpenCode verification output\n", encoding="utf-8")

    session = InstallerSession(
        install_root=str(install_root),
        opencode_log_path=str(temp_opencode_log),
    )

    def fail_promotion(*args, **kwargs):
        raise OSError("simulated promotion failure")

    monkeypatch.setattr(reporting_module, "_promote_staged_artifacts", fail_promotion)

    with pytest.raises(OSError, match="simulated promotion failure"):
        persist_install_root_reports(session)

    assert session.opencode_log_path == str(temp_opencode_log)
    assert not (install_root / "logs" / "opencode-verification.log").exists()


def test_persist_install_root_reports_rolls_back_partial_promotion_with_opencode_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    install_root = tmp_path / "install-root"
    log_path = install_root / "logs" / "install.log"
    report_path = install_root / "logs" / "install-report.json"
    session_path = install_root / "config" / "installer-session.json"
    opencode_log_path = install_root / "logs" / "opencode-verification.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("stale log\n", encoding="utf-8")
    report_path.write_text("{\"stale\": \"report\"}\n", encoding="utf-8")
    session_path.write_text("{\"stale\": \"session\"}\n", encoding="utf-8")
    opencode_log_path.write_bytes(b"old-opencode-log\n")

    temp_opencode_log = tmp_path / "temp-run" / "opencode-verification.log"
    temp_opencode_log.parent.mkdir(parents=True, exist_ok=True)
    temp_opencode_log.write_bytes(b"new-opencode-log\n")

    session = InstallerSession(
        install_root=str(install_root),
        bootstrap_status="ready",
        opencode_log_path=str(temp_opencode_log),
    )

    original_replace = Path.replace
    failure_injected = False

    def fail_after_partial_promotions(self: Path, target: Path):
        nonlocal failure_injected
        if (
            not failure_injected
            and self.name == "opencode-verification.log"
            and target == opencode_log_path
        ):
            failure_injected = True
            raise OSError("simulated partial promotion failure")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_after_partial_promotions)

    with pytest.raises(OSError, match="simulated partial promotion failure"):
        persist_install_root_reports(session)

    assert session.opencode_log_path == str(temp_opencode_log)
    assert log_path.read_text(encoding="utf-8") == "stale log\n"
    assert report_path.read_text(encoding="utf-8") == "{\"stale\": \"report\"}\n"
    assert session_path.read_text(encoding="utf-8") == "{\"stale\": \"session\"}\n"
    assert opencode_log_path.read_bytes() == b"old-opencode-log\n"
