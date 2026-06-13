from __future__ import annotations

import subprocess
import threading
import time


TAILSCALE_IP_CACHE_TTL_SECONDS = 30.0
_TAILSCALE_IP_CACHE_LOCK = threading.Lock()
_TAILSCALE_IP_CACHE: tuple[float, str] | None = None


def detect_tailscale_ip() -> str:
    global _TAILSCALE_IP_CACHE

    now = time.monotonic()
    with _TAILSCALE_IP_CACHE_LOCK:
        cached_payload = _TAILSCALE_IP_CACHE
        if cached_payload is not None:
            cached_at, cached_ip = cached_payload
            if (now - cached_at) <= TAILSCALE_IP_CACHE_TTL_SECONDS:
                return cached_ip
    try:
        completed = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError:
        with _TAILSCALE_IP_CACHE_LOCK:
            _TAILSCALE_IP_CACHE = (time.monotonic(), "")
        return ""

    if completed.returncode != 0:
        with _TAILSCALE_IP_CACHE_LOCK:
            _TAILSCALE_IP_CACHE = (time.monotonic(), "")
        return ""

    for line in completed.stdout.splitlines():
        candidate = line.strip()
        if candidate:
            with _TAILSCALE_IP_CACHE_LOCK:
                _TAILSCALE_IP_CACHE = (time.monotonic(), candidate)
            return candidate
    with _TAILSCALE_IP_CACHE_LOCK:
        _TAILSCALE_IP_CACHE = (time.monotonic(), "")
    return ""
