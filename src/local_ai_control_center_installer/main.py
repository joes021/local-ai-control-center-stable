from collections.abc import Callable
from datetime import datetime, timezone
import os
from pathlib import Path
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
    install_root = (
        os.environ.get("LACC_INSTALLER_PREFILL_ROOT")
        or os.environ.get("LOCAL_AI_CONTROL_CENTER_INSTALLER_PREFILL_ROOT")
        or None
    )
    normalized_install_root = None
    existing_install_detected = False
    if install_root:
        normalized_install_root = str(Path(install_root).expanduser().resolve())
        existing_install_detected = Path(normalized_install_root).exists()
    return InstallerSession(
        platform=platform_module.system().lower(),
        started_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        install_root=normalized_install_root,
        existing_install_detected=existing_install_detected,
    )


def run_installer(
    *,
    collect_answers: SessionStep | None = None,
    scan_dependencies: SessionStep | None = None,
    apply_phase: SessionStep | None = None,
    prepare_download_plan: SessionStep | None = None,
    apply_runtime_payload: SessionStep | None = None,
    apply_server_verification: SessionStep | None = None,
    apply_opencode_bootstrap: SessionStep | None = None,
    apply_opencode_verification: SessionStep | None = None,
    apply_turboquant: SessionStep | None = None,
    apply_first_run_validation: SessionStep | None = None,
    apply_control_center_integration: SessionStep | None = None,
    apply_product_gate: SessionStep | None = None,
    write_reports: ReportStep | None = None,
):
    collect_answers = collect_answers or defaults_module.default_collect_answers
    scan_dependencies = scan_dependencies or defaults_module.default_scan_dependencies
    apply_phase = apply_phase or defaults_module.default_apply_phase
    prepare_download_plan = (
        prepare_download_plan or defaults_module.default_prepare_download_plan
    )
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
    apply_turboquant = apply_turboquant or defaults_module.default_apply_turboquant
    apply_first_run_validation = (
        apply_first_run_validation
        or defaults_module.default_apply_first_run_validation
    )
    apply_control_center_integration = (
        apply_control_center_integration
        or defaults_module.default_apply_control_center_integration
    )
    apply_product_gate = apply_product_gate or defaults_module.default_apply_product_gate
    write_reports = write_reports or defaults_module.default_write_reports

    session = build_default_session()
    session = collect_answers(session)
    session = scan_dependencies(session)
    session = apply_phase(session)
    session = prepare_download_plan(session)
    session = apply_runtime_payload(session)
    session = apply_server_verification(session)
    session = apply_opencode_bootstrap(session)
    session = apply_opencode_verification(session)
    session = apply_turboquant(session)
    session = apply_first_run_validation(session)
    session = apply_control_center_integration(session)
    session = apply_product_gate(session)
    write_reports(session)
    return session.to_dict()


def main() -> int:
    try:
        result = run_installer()
    except (PromptCancelledError, StarterModelCatalogError) as error:
        print(str(error), file=sys.stderr)
        return 1
    if result.get("product_installation_status") == "complete":
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
