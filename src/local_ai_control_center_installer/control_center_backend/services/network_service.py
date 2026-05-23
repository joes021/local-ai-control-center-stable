from __future__ import annotations

import subprocess


def detect_tailscale_ip() -> str:
    try:
        completed = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return ""

    if completed.returncode != 0:
        return ""

    for line in completed.stdout.splitlines():
        candidate = line.strip()
        if candidate:
            return candidate
    return ""
