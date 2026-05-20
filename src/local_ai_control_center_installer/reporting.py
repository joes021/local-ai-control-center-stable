from dataclasses import dataclass
import json
from pathlib import Path

from local_ai_control_center_installer.session import InstallerSession


@dataclass
class RunPaths:
    run_dir: Path
    log_path: Path
    json_report_path: Path


def build_run_paths(temp_root: Path, run_id: str) -> RunPaths:
    run_dir = temp_root / "LocalAIControlCenterInstaller" / "runs" / run_id
    return RunPaths(
        run_dir=run_dir,
        log_path=run_dir / "install.log",
        json_report_path=run_dir / "install-report.json",
    )


def write_human_log(session: InstallerSession, log_path: Path) -> Path:
    lines = [
        f"Install root: {session.install_root}",
        f"Bootstrap status: {session.bootstrap_status}",
        f"Product installation status: {session.product_installation_status}",
        f"Failing step: {session.failing_step}",
        "Dependencies:",
    ]
    lines.extend(
        f"{dependency.name}: {dependency.status}"
        for dependency in session.dependencies
    )
    _write_text(log_path, "\n".join(lines) + "\n")
    return log_path


def write_json_report(session: InstallerSession, report_path: Path) -> Path:
    payload = {
        "bootstrap_status": session.bootstrap_status,
        "product_installation_status": session.product_installation_status,
        "failing_step": session.failing_step,
        "dependencies": [dependency.to_dict() for dependency in session.dependencies],
        "install_root": session.install_root,
    }
    _write_text(report_path, json.dumps(payload, indent=2))
    return report_path


def write_session_snapshot(session: InstallerSession, session_path: Path) -> Path:
    _write_text(session_path, json.dumps(session.to_dict(), indent=2))
    return session_path


def _write_text(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
