from __future__ import annotations

from pathlib import Path
import sys

_REPO_SRC = Path(__file__).resolve().parents[1] / "src"
if _REPO_SRC.is_dir():
    sys.path.insert(0, str(_REPO_SRC))

from local_ai_control_center_installer.windows_release import (
    run_windows_installer_entry,
)


if __name__ == "__main__":
    raise SystemExit(run_windows_installer_entry())
