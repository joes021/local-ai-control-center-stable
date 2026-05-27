from __future__ import annotations

import shutil
import subprocess

from local_ai_control_center_installer.control_center_backend.services.state_helpers import (
    action_result,
)
from local_ai_control_center_installer.platform_paths import is_windows_platform


def pick_local_gguf() -> dict[str, object]:
    if not is_windows_platform():
        return _run_linux_picker_command(
            ["zenity", "--file-selection", "--file-filter=GGUF files | *.gguf"],
            action="pick-local-gguf",
            missing_picker_message=(
                "Linux picker nije dostupan. Instaliraj zenity ili upiši putanju ručno."
            ),
        )

    command = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$dialog = New-Object System.Windows.Forms.OpenFileDialog; "
        "$dialog.Filter = 'GGUF files (*.gguf)|*.gguf|All files (*.*)|*.*'; "
        "$dialog.Multiselect = $false; "
        "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { "
        "  Write-Output $dialog.FileName "
        "}"
    )
    return _run_picker_command(command, action="pick-local-gguf")


def pick_working_directory() -> dict[str, object]:
    if not is_windows_platform():
        return _run_linux_picker_command(
            ["zenity", "--file-selection", "--directory"],
            action="pick-working-directory",
            missing_picker_message=(
                "Linux picker nije dostupan. Instaliraj zenity ili upiši putanju ručno."
            ),
        )

    command = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
        "$dialog.ShowNewFolderButton = $true; "
        "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { "
        "  Write-Output $dialog.SelectedPath "
        "}"
    )
    return _run_picker_command(command, action="pick-working-directory")


def _run_picker_command(command: str, *, action: str) -> dict[str, object]:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return action_result(
            "error",
            action,
            "Windows picker nije uspeo da se otvori.",
            stderr=completed.stderr.strip() or "Windows picker nije uspeo da se otvori.",
        )

    path = completed.stdout.strip()
    if not path:
        return {
            "status": "cancelled",
            "summary": "Izbor je otkazan.",
            "path": "",
        }
    return {
        "status": "ok",
        "summary": "Putanja je izabrana.",
        "path": path,
    }


def _run_linux_picker_command(
    command: list[str],
    *,
    action: str,
    missing_picker_message: str,
) -> dict[str, object]:
    if not shutil.which(command[0]):
        return action_result(
            "error",
            action,
            missing_picker_message,
            stderr=missing_picker_message,
        )

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode not in {0, 1}:
        return action_result(
            "error",
            action,
            "Linux picker nije uspeo da se otvori.",
            stderr=completed.stderr.strip() or "Linux picker nije uspeo da se otvori.",
        )

    path = completed.stdout.strip()
    if not path:
        return {
            "status": "cancelled",
            "summary": "Izbor je otkazan.",
            "path": "",
        }
    return {
        "status": "ok",
        "summary": "Putanja je izabrana.",
        "path": path,
    }
