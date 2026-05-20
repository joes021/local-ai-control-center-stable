from collections.abc import Callable
from datetime import datetime, timezone
import platform as platform_module

from local_ai_control_center_installer.session import InstallerSession


SessionStep = Callable[[InstallerSession], InstallerSession]
ReportStep = Callable[[InstallerSession], None]


def build_default_session() -> InstallerSession:
    return InstallerSession(
        platform=platform_module.system().lower(),
        started_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )


def run_installer(
    *,
    collect_answers: SessionStep | None = None,
    scan_dependencies: SessionStep | None = None,
    apply_phase: SessionStep | None = None,
    write_reports: ReportStep | None = None,
):
    session = build_default_session()
    session = (collect_answers or _identity_session_step)(session)
    session = (scan_dependencies or _identity_session_step)(session)
    session = (apply_phase or _identity_session_step)(session)
    (write_reports or _noop_report_step)(session)
    return session.to_dict()


def _identity_session_step(session: InstallerSession) -> InstallerSession:
    return session


def _noop_report_step(session: InstallerSession) -> None:
    del session
