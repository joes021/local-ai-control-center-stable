from collections.abc import Callable
from datetime import datetime, timezone
import platform as platform_module
import sys

import local_ai_control_center_installer.defaults as defaults_module
from local_ai_control_center_installer.prompts import (
    PromptCancelledError,
    StarterModelCatalogError,
)
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
    apply_runtime_payload: SessionStep | None = None,
    apply_server_verification: SessionStep | None = None,
    apply_opencode_bootstrap: SessionStep | None = None,
    apply_opencode_verification: SessionStep | None = None,
    write_reports: ReportStep | None = None,
):
    collect_answers = collect_answers or defaults_module.default_collect_answers
    scan_dependencies = scan_dependencies or defaults_module.default_scan_dependencies
    apply_phase = apply_phase or defaults_module.default_apply_phase
    apply_runtime_payload = (
        apply_runtime_payload or defaults_module.default_apply_runtime_payload
    )
    apply_server_verification = (
        apply_server_verification
        or defaults_module.default_apply_server_verification
    )
    apply_opencode_bootstrap = (
        apply_opencode_bootstrap or defaults_module.default_apply_opencode_bootstrap
    )
    apply_opencode_verification = (
        apply_opencode_verification
        or defaults_module.default_apply_opencode_verification
    )
    write_reports = write_reports or defaults_module.default_write_reports

    session = build_default_session()
    session = collect_answers(session)
    session = scan_dependencies(session)
    session = apply_phase(session)
    session = apply_runtime_payload(session)
    session = apply_server_verification(session)
    session = apply_opencode_bootstrap(session)
    session = apply_opencode_verification(session)
    write_reports(session)
    return session.to_dict()


def main() -> int:
    try:
        result = run_installer()
    except (PromptCancelledError, StarterModelCatalogError) as error:
        print(str(error), file=sys.stderr)
        return 1
    opencode_requested = result.get("install_opencode") is True
    opencode_ready = result.get("opencode_verification_status") == "ready"
    if (
        result.get("bootstrap_status") == "ready"
        and result.get("runtime_payload_status") == "ready"
        and result.get("server_verification_status") == "ready"
        and (not opencode_requested or opencode_ready)
    ):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
