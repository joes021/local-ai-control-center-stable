from pathlib import Path
import shutil
import sys
import tempfile

from local_ai_control_center_installer.apply_phase import apply_bootstrap_phase
from local_ai_control_center_installer.dependencies import scan_all_dependencies
from local_ai_control_center_installer.prompts import collect_installer_answers
from local_ai_control_center_installer.reporting import (
    build_run_paths,
    write_human_log,
    write_json_report,
)
from local_ai_control_center_installer.session import InstallerSession


def default_collect_answers(session: InstallerSession) -> InstallerSession:
    return collect_installer_answers(session)


def default_scan_dependencies(session: InstallerSession) -> InstallerSession:
    return scan_all_dependencies(
        session,
        probes={
            "python": _probe_python,
            "git": _probe_command("git"),
            "node": _probe_command("node"),
            "build-tools": _probe_command(
                "cl",
                "gcc",
                "clang",
                "cmake",
                "nmake",
                "make",
            ),
        },
    )


def default_apply_phase(session: InstallerSession) -> InstallerSession:
    return apply_bootstrap_phase(session, temp_root=_default_temp_root())


def default_write_reports(session: InstallerSession) -> None:
    run_paths = build_run_paths(_default_temp_root(), _build_run_id(session))
    write_human_log(session, run_paths.log_path)
    write_json_report(session, run_paths.json_report_path)


def _default_temp_root() -> Path:
    return Path(tempfile.gettempdir())


def _build_run_id(session: InstallerSession) -> str:
    if session.started_at:
        return session.started_at.replace(":", "-")
    return "manual-run"


def _probe_python() -> str | None:
    if Path(sys.executable).exists():
        return sys.executable
    return _find_first_available("python", "python3")


def _probe_command(*names: str):
    def probe() -> str | None:
        return _find_first_available(*names)

    return probe


def _find_first_available(*names: str) -> str | None:
    for name in names:
        detected = shutil.which(name)
        if detected:
            return detected
    return None
