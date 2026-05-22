from __future__ import annotations

from collections.abc import Callable
import sys

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
    pause_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    frozen: bool | None = None,
) -> int:
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
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
