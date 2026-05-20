from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from local_ai_control_center_installer.reporting import (
    build_run_paths,
    write_human_log,
    write_json_report,
    write_session_snapshot,
)
from local_ai_control_center_installer.session import InstallerSession


def apply_bootstrap_phase(
    session: InstallerSession,
    temp_root: Path,
) -> InstallerSession:
    install_root = _require_install_root(session)
    run_paths = build_run_paths(temp_root, _build_run_id(session))
    session.product_installation_status = "incomplete"

    if any(
        dependency.required and dependency.status != "ready"
        for dependency in session.dependencies
    ):
        session.bootstrap_status = "failed"
        session.failing_step = "dependency-bootstrap"
        _write_temp_run_artifacts(session, run_paths)
        return session

    ready_session = _build_ready_session(session)
    _write_temp_run_artifacts(ready_session, run_paths)

    try:
        _persist_install_root_artifacts(ready_session, install_root)
    except OSError as exc:
        session.bootstrap_status = "failed"
        session.failing_step = "install-root-persistence"
        session.error_message = str(exc)
        _write_temp_run_artifacts(session, run_paths)
    else:
        session.bootstrap_status = ready_session.bootstrap_status
        session.failing_step = ready_session.failing_step
        session.error_message = ready_session.error_message

    return session


def _build_run_id(session: InstallerSession) -> str:
    if session.started_at:
        return session.started_at.replace(":", "-")
    return _generate_fallback_run_id()


def _require_install_root(session: InstallerSession) -> Path:
    install_root = (session.install_root or "").strip()
    if not install_root:
        raise ValueError("session.install_root is required for bootstrap apply phase")
    normalized_install_root = Path(install_root)
    session.install_root = str(normalized_install_root)
    return normalized_install_root


def _generate_fallback_run_id() -> str:
    return uuid4().hex


def _build_ready_session(session: InstallerSession) -> InstallerSession:
    ready_session = deepcopy(session)
    ready_session.bootstrap_status = "ready"
    ready_session.failing_step = None
    ready_session.product_installation_status = "incomplete"
    ready_session.error_message = None
    return ready_session


def _persist_install_root_artifacts(session: InstallerSession, install_root: Path) -> None:
    install_root_preexisting = install_root.exists()
    staging_root = install_root / f".staging-{uuid4().hex}"
    artifact_paths = _build_artifact_paths(install_root)
    staged_artifact_paths = _build_artifact_paths(staging_root)
    try:
        write_human_log(session, staged_artifact_paths[0])
        write_json_report(session, staged_artifact_paths[1])
        write_session_snapshot(session, staged_artifact_paths[2])
        _promote_staged_artifacts(
            install_root,
            staging_root,
            staged_artifact_paths,
            artifact_paths,
        )
    except OSError:
        _cleanup_staging_root(staging_root)
        if not install_root_preexisting:
            _remove_empty_directory(install_root)
        raise
    _cleanup_staging_root(staging_root)


def _write_temp_run_artifacts(session: InstallerSession, run_paths) -> None:
    write_human_log(session, run_paths.log_path)
    write_json_report(session, run_paths.json_report_path)


def _build_artifact_paths(root: Path) -> list[Path]:
    logs_dir = root / "logs"
    config_dir = root / "config"
    return [
        logs_dir / "install.log",
        logs_dir / "install-report.json",
        config_dir / "installer-session.json",
    ]


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
