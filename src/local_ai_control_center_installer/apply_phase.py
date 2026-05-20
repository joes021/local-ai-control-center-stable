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

    try:
        _persist_install_root_artifacts(_build_ready_session(session), install_root)
    except OSError as exc:
        session.bootstrap_status = "failed"
        session.failing_step = "install-root-persistence"
        session.error_message = str(exc)
    else:
        session.bootstrap_status = "ready"
        session.failing_step = None
        session.error_message = None

    _write_temp_run_artifacts(session, run_paths)

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
    logs_dir = install_root / "logs"
    config_dir = install_root / "config"
    logs_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)
    write_human_log(session, logs_dir / "install.log")
    write_json_report(session, logs_dir / "install-report.json")
    write_session_snapshot(session, config_dir / "installer-session.json")


def _write_temp_run_artifacts(session: InstallerSession, run_paths) -> None:
    write_human_log(session, run_paths.log_path)
    write_json_report(session, run_paths.json_report_path)
