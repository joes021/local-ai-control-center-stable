from __future__ import annotations

from collections.abc import Callable
import sys

from local_ai_control_center_installer.control_center_panel import (
    run_control_center_panel_entry,
)
from local_ai_control_center_installer.control_center_uninstall import (
    run_control_center_uninstall_entry,
)
from local_ai_control_center_installer.main import main


def build_versioned_setup_name(version: str) -> str:
    normalized = version.strip()
    if normalized.lower().startswith("v"):
        normalized = normalized[1:].strip()
    if not normalized:
        raise ValueError("version is required")
    return f"LocalAIControlCenterSetup-v{normalized}.exe"


def run_windows_installer_entry(
    *,
    main_fn: Callable[[], int] = main,
    panel_main_fn: Callable[[list[str] | None], int] = run_control_center_panel_entry,
    uninstall_main_fn: Callable[[list[str] | None], int] = run_control_center_uninstall_entry,
    pause_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    frozen: bool | None = None,
    argv: list[str] | None = None,
) -> int:
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    argv = list(sys.argv if argv is None else argv)
    if "--panel" in argv:
        panel_index = argv.index("--panel")
        return panel_main_fn(argv[panel_index + 1 :])
    if "--uninstall" in argv:
        uninstall_index = argv.index("--uninstall")
        return uninstall_main_fn(argv[uninstall_index + 1 :])
    try:
        return main_fn()
    finally:
        if frozen:
            sys.stdout.flush()
            sys.stderr.flush()
            try:
                pause_fn("Press Enter to close the installer window...")
            except EOFError:
                pass
            except KeyboardInterrupt:
                output_fn("")
