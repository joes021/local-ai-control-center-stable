from __future__ import annotations

from collections.abc import Callable
import sys

from local_ai_control_center_installer.control_center_panel import (
    run_control_center_panel_entry,
)
from local_ai_control_center_installer.control_center_uninstall import (
    run_control_center_uninstall_entry,
)
from local_ai_control_center_installer.control_center_backend.workers.model_download_worker import (
    run_model_download_worker_entry,
)
from local_ai_control_center_installer.control_center_backend.workers.update_install_worker import (
    run_update_install_worker_entry,
)
from local_ai_control_center_installer.main import main
from local_ai_control_center_installer.platform_paths import run_release_entry


def build_versioned_setup_name(version: str) -> str:
    normalized = version.strip()
    if normalized.lower().startswith("v"):
        normalized = normalized[1:].strip()
    if not normalized:
        raise ValueError("version is required")
    return f"RuntimePilotSetup-v{normalized}.exe"


def run_windows_installer_entry(
    *,
    main_fn: Callable[[], int] = main,
    panel_main_fn: Callable[[list[str] | None], int] = run_control_center_panel_entry,
    uninstall_main_fn: Callable[[list[str] | None], int] = run_control_center_uninstall_entry,
    update_worker_main_fn: Callable[[list[str] | None], int] = run_update_install_worker_entry,
    model_download_worker_main_fn: Callable[[list[str] | None], int] = run_model_download_worker_entry,
    pause_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    frozen: bool | None = None,
    argv: list[str] | None = None,
) -> int:
    return run_release_entry(
        main_fn=main_fn,
        panel_main_fn=panel_main_fn,
        uninstall_main_fn=uninstall_main_fn,
        update_worker_main_fn=update_worker_main_fn,
        model_download_worker_main_fn=model_download_worker_main_fn,
        pause_fn=pause_fn,
        output_fn=output_fn,
        frozen=frozen,
        argv=argv,
        pause_in_frozen_mode=True,
    )
