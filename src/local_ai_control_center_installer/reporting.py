from dataclasses import dataclass
import json
from pathlib import Path
from uuid import uuid4

from local_ai_control_center_installer.session import InstallerSession


@dataclass
class RunPaths:
    run_dir: Path
    log_path: Path
    json_report_path: Path
    server_log_path: Path
    opencode_log_path: Path


def build_run_paths(temp_root: Path, run_id: str) -> RunPaths:
    run_dir = temp_root / "LocalAIControlCenterInstaller" / "runs" / run_id
    return RunPaths(
        run_dir=run_dir,
        log_path=run_dir / "install.log",
        json_report_path=run_dir / "install-report.json",
        server_log_path=run_dir / "llama-server.log",
        opencode_log_path=run_dir / "opencode-verification.log",
    )


def write_human_log(
    session: InstallerSession,
    log_path: Path,
    *,
    allowed_opencode_log_path: Path | None = None,
) -> Path:
    _normalize_session_opencode_log_path(
        session,
        allowed_path=allowed_opencode_log_path,
    )
    lines = [
        f"Install root: {session.install_root}",
        f"Bootstrap status: {session.bootstrap_status}",
        f"Product installation status: {session.product_installation_status}",
        f"Runtime payload status: {session.runtime_payload_status}",
        f"Runtime artifact status: {session.runtime_artifact_status}",
        f"Starter model status: {session.starter_model_status}",
        f"Active model config status: {session.active_model_config_status}",
        f"Server verification status: {session.server_verification_status}",
        f"Server process status: {session.server_process_status}",
        f"Server health status: {session.server_health_status}",
        f"OpenCode artifact status: {session.opencode_artifact_status}",
        f"OpenCode verification status: {session.opencode_verification_status}",
        f"OpenCode process status: {session.opencode_process_status}",
        f"OpenCode live-route status: {session.opencode_connection_status}",
        f"Pinned runtime artifact id: {session.runtime_artifact_id}",
        f"Selected starter model: {session.starter_model}",
        f"Runtime artifact path: {session.runtime_artifact_path}",
        f"Starter model path: {session.starter_model_path}",
        f"Active model config path: {session.active_model_config_path}",
        f"Runtime metadata path: {session.runtime_metadata_path}",
        f"OpenCode artifact id: {session.opencode_artifact_id}",
        f"OpenCode artifact path: {session.opencode_artifact_path}",
        f"OpenCode metadata path: {session.opencode_metadata_path}",
        f"OpenCode config path: {session.opencode_config_path}",
        f"Verified OpenCode command: {session.verified_opencode_command}",
        f"Verified server port: {session.verified_server_port}",
        f"Verified server URL: {session.verified_server_url}",
        f"OpenCode log path: {session.opencode_log_path}",
        f"Server log path: {session.server_log_path}",
        f"Failing step: {session.failing_step}",
        "Dependencies:",
    ]
    lines.extend(
        f"{dependency.name}: {dependency.status}"
        for dependency in session.dependencies
    )
    _write_text(log_path, "\n".join(lines) + "\n")
    return log_path


def write_json_report(
    session: InstallerSession,
    report_path: Path,
    *,
    allowed_opencode_log_path: Path | None = None,
) -> Path:
    _normalize_session_opencode_log_path(
        session,
        allowed_path=allowed_opencode_log_path,
    )
    payload = {
        "bootstrap_status": session.bootstrap_status,
        "product_installation_status": session.product_installation_status,
        "runtime_payload_status": session.runtime_payload_status,
        "runtime_artifact_status": session.runtime_artifact_status,
        "starter_model_status": session.starter_model_status,
        "active_model_config_status": session.active_model_config_status,
        "server_verification_status": session.server_verification_status,
        "server_process_status": session.server_process_status,
        "server_health_status": session.server_health_status,
        "opencode_artifact_status": session.opencode_artifact_status,
        "opencode_verification_status": session.opencode_verification_status,
        "opencode_process_status": session.opencode_process_status,
        "opencode_connection_status": session.opencode_connection_status,
        "failing_step": session.failing_step,
        "dependencies": [dependency.to_dict() for dependency in session.dependencies],
        "install_root": session.install_root,
        "runtime_artifact_id": session.runtime_artifact_id,
        "starter_model": session.starter_model,
        "runtime_artifact_path": session.runtime_artifact_path,
        "starter_model_path": session.starter_model_path,
        "active_model_config_path": session.active_model_config_path,
        "runtime_metadata_path": session.runtime_metadata_path,
        "opencode_artifact_id": session.opencode_artifact_id,
        "opencode_artifact_path": session.opencode_artifact_path,
        "opencode_metadata_path": session.opencode_metadata_path,
        "opencode_config_path": session.opencode_config_path,
        "verified_opencode_command": session.verified_opencode_command,
        "verified_server_port": session.verified_server_port,
        "verified_server_url": session.verified_server_url,
        "opencode_log_path": session.opencode_log_path,
        "server_log_path": session.server_log_path,
        "error_message": session.error_message,
    }
    _write_text(report_path, json.dumps(payload, indent=2))
    return report_path


def write_session_snapshot(
    session: InstallerSession,
    session_path: Path,
    *,
    allowed_opencode_log_path: Path | None = None,
) -> Path:
    _normalize_session_opencode_log_path(
        session,
        allowed_path=allowed_opencode_log_path,
    )
    _write_text(session_path, json.dumps(session.to_dict(), indent=2))
    return session_path


def persist_install_root_reports(session: InstallerSession) -> None:
    install_root = _require_install_root(session)
    _normalize_session_opencode_log_path(session)
    install_root_preexisting = install_root.exists()
    staging_root = install_root / f".staging-{uuid4().hex}"
    artifact_paths = _build_artifact_paths(install_root)
    staged_artifact_paths = _build_artifact_paths(staging_root)
    original_opencode_log_path = session.opencode_log_path

    try:
        persisted_opencode_log_path = _stage_optional_opencode_log(
            session,
            install_root,
            staging_root,
            artifact_paths,
            staged_artifact_paths,
        )
        if persisted_opencode_log_path is not None:
            session.opencode_log_path = str(persisted_opencode_log_path)
        write_human_log(
            session,
            staged_artifact_paths[0],
            allowed_opencode_log_path=persisted_opencode_log_path,
        )
        write_json_report(
            session,
            staged_artifact_paths[1],
            allowed_opencode_log_path=persisted_opencode_log_path,
        )
        write_session_snapshot(
            session,
            staged_artifact_paths[2],
            allowed_opencode_log_path=persisted_opencode_log_path,
        )
        _promote_staged_artifacts(
            install_root,
            staging_root,
            staged_artifact_paths,
            artifact_paths,
        )
    except OSError:
        session.opencode_log_path = original_opencode_log_path
        _cleanup_staging_root(staging_root)
        if not install_root_preexisting:
            _remove_empty_directory(install_root)
        raise

    _cleanup_staging_root(staging_root)


def _write_text(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def _write_bytes(path: Path, contents: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)


def _require_install_root(session: InstallerSession) -> Path:
    install_root = (session.install_root or "").strip()
    if not install_root:
        raise ValueError("session.install_root is required to persist reports")
    normalized_install_root = Path(install_root)
    session.install_root = str(normalized_install_root)
    return normalized_install_root


def _normalize_optional_existing_file(
    raw_path: str | None,
    *,
    allowed_path: Path | None = None,
) -> str | None:
    normalized = (raw_path or "").strip()
    if not normalized:
        return None

    candidate_path = Path(normalized)
    if allowed_path is not None and candidate_path == allowed_path:
        return str(candidate_path)
    if not candidate_path.exists() or not candidate_path.is_file():
        return None

    return str(candidate_path)


def _normalize_session_opencode_log_path(
    session: InstallerSession,
    *,
    allowed_path: Path | None = None,
) -> None:
    session.opencode_log_path = _normalize_optional_existing_file(
        session.opencode_log_path,
        allowed_path=allowed_path,
    )


def _build_artifact_paths(root: Path) -> list[Path]:
    logs_dir = root / "logs"
    config_dir = root / "config"
    return [
        logs_dir / "install.log",
        logs_dir / "install-report.json",
        config_dir / "installer-session.json",
    ]


def _stage_optional_opencode_log(
    session: InstallerSession,
    install_root: Path,
    staging_root: Path,
    artifact_paths: list[Path],
    staged_artifact_paths: list[Path],
) -> Path | None:
    opencode_log_path = (session.opencode_log_path or "").strip()
    if not opencode_log_path:
        return None

    source_path = Path(opencode_log_path)
    if not source_path.exists() or not source_path.is_file():
        return None

    target_path = install_root / "logs" / "opencode-verification.log"
    staged_target_path = staging_root / target_path.relative_to(install_root)
    _write_bytes(staged_target_path, source_path.read_bytes())
    artifact_paths.append(target_path)
    staged_artifact_paths.append(staged_target_path)
    return target_path


def _promote_staged_artifacts(
    install_root: Path,
    staging_root: Path,
    staged_artifact_paths: list[Path],
    artifact_paths: list[Path],
) -> None:
    promotion_records: list[dict[str, Path | bool]] = []
    created_directories: list[Path] = []

    try:
        for staged_artifact_path, artifact_path in zip(staged_artifact_paths, artifact_paths):
            parent_directory = artifact_path.parent
            parent_existed = parent_directory.exists()
            if not parent_existed:
                parent_directory.mkdir(parents=True, exist_ok=True)
                created_directories.append(parent_directory)

            backup_path = staging_root / "backups" / artifact_path.relative_to(install_root)
            record: dict[str, Path | bool] = {
                "artifact_path": artifact_path,
                "backup_path": backup_path,
                "had_existing_target": artifact_path.exists(),
                "backup_created": False,
                "promoted": False,
            }
            promotion_records.append(record)

            if record["had_existing_target"]:
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                artifact_path.replace(backup_path)
                record["backup_created"] = True

            staged_artifact_path.replace(artifact_path)
            record["promoted"] = True
    except OSError:
        _rollback_promoted_artifacts(promotion_records, created_directories)
        raise


def _rollback_promoted_artifacts(
    promotion_records: list[dict[str, Path | bool]],
    created_directories: list[Path],
) -> None:
    for record in reversed(promotion_records):
        artifact_path = record["artifact_path"]
        backup_path = record["backup_path"]

        if record["promoted"]:
            try:
                artifact_path.unlink()
            except FileNotFoundError:
                pass

        if record["backup_created"]:
            backup_path.replace(artifact_path)

    for directory in reversed(created_directories):
        _remove_empty_directory(directory)


def _cleanup_staging_root(staging_root: Path) -> None:
    if not staging_root.exists():
        return

    for path in sorted(staging_root.rglob("*"), reverse=True):
        try:
            if path.is_file():
                path.unlink()
            else:
                path.rmdir()
        except OSError:
            continue
    _remove_empty_directory(staging_root)


def _remove_empty_directory(directory: Path) -> None:
    try:
        directory.rmdir()
    except OSError:
        pass
