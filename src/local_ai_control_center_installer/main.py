from datetime import datetime, timezone
from pathlib import Path
import platform as platform_module
import sys
import tempfile

from local_ai_control_center_installer.apply_phase import (
    apply_bootstrap_phase as _apply_bootstrap_phase,
)
from local_ai_control_center_installer.dependencies import (
    scan_all_dependencies as _scan_all_dependencies,
)
from local_ai_control_center_installer.prompts import (
    DEFAULT_INSTALL_ROOT,
    collect_installer_answers as _collect_installer_answers,
)
from local_ai_control_center_installer.session import InstallerSession


def build_default_session() -> InstallerSession:
    return InstallerSession(
        platform=platform_module.system().lower(),
        started_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )


def collect_installer_answers(session: InstallerSession) -> InstallerSession:
    if sys.stdin is None or not sys.stdin.isatty():
        return session
    return _collect_installer_answers(session)


def scan_all_dependencies(session: InstallerSession) -> InstallerSession:
    return _scan_all_dependencies(
        session,
        probes={
            "python": _missing_probe,
            "git": _missing_probe,
            "node": _missing_probe,
            "build-tools": _missing_probe,
        },
    )


def apply_bootstrap_phase(session: InstallerSession) -> InstallerSession:
    if not session.install_root:
        session.install_root = DEFAULT_INSTALL_ROOT
    return _apply_bootstrap_phase(session, temp_root=Path(tempfile.gettempdir()))


def write_reports(session: InstallerSession) -> None:
    return None


def run_installer(
    *,
    collect_answers=collect_installer_answers,
    scan_dependencies=scan_all_dependencies,
    apply_phase=apply_bootstrap_phase,
    write_reports=write_reports,
):
    session = build_default_session()
    session = collect_answers(session)
    session = scan_dependencies(session)
    session = apply_phase(session)
    write_reports(session)
    return session.to_dict()


def _missing_probe() -> None:
    return None
