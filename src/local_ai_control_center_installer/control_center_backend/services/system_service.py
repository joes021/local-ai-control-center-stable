from __future__ import annotations

import subprocess

from local_ai_control_center_installer.control_center_backend.services.state_helpers import (
    action_result,
)


def pick_local_gguf() -> dict[str, object]:
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
