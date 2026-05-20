from pathlib import Path

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
    logs_dir = install_root / "logs"
    config_dir = install_root / "config"
    run_paths = build_run_paths(temp_root, _build_run_id(session))

    logs_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)

    if any(
        dependency.required and dependency.status != "ready"
        for dependency in session.dependencies
    ):
        session.bootstrap_status = "failed"
        session.failing_step = "dependency-bootstrap"
    else:
        session.bootstrap_status = "ready"
        session.failing_step = None

    session.product_installation_status = "incomplete"

    write_human_log(session, run_paths.log_path)
    write_json_report(session, run_paths.json_report_path)
    write_human_log(session, logs_dir / "install.log")
    if session.bootstrap_status == "ready":
        write_json_report(session, logs_dir / "install-report.json")
    write_session_snapshot(session, config_dir / "installer-session.json")

    return session


def _build_run_id(session: InstallerSession) -> str:
    return (session.started_at or "manual-run").replace(":", "-")


def _require_install_root(session: InstallerSession) -> Path:
    install_root = (session.install_root or "").strip()
    if not install_root:
        raise ValueError("session.install_root is required for bootstrap apply phase")
    return Path(install_root)
