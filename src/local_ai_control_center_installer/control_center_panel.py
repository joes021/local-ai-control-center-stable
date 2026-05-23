from __future__ import annotations

import argparse
import os
import socket
import subprocess
import threading
import time
from urllib.error import URLError
from urllib.request import urlopen

import uvicorn

from local_ai_control_center_installer.control_center_backend.main import app


DEFAULT_UI_HOST = "127.0.0.1"
DEFAULT_UI_PORT = 3210


def run_control_center_panel_entry(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-root", required=True)
    parser.add_argument("--host", default=DEFAULT_UI_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_UI_PORT)
    parser.add_argument("--access-mode", default="local-only")
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args(argv)

    os.environ["LACC_INSTALL_ROOT"] = args.install_root
    os.environ["LACC_UI_PORT"] = str(args.port)
    os.environ["LACC_UI_ACCESS_MODE"] = args.access_mode
    url = f"http://{args.host}:{args.port}/"

    if _health_ready(url):
        if args.open_browser:
            _open_url(url)
        return 0
    if _port_in_use(args.host, args.port):
        raise RuntimeError(f"UI port {args.port} je vec zauzet drugim procesom.")

    if args.open_browser:
        threading.Thread(
            target=_open_when_ready,
            args=(url,),
            daemon=True,
        ).start()

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


def _open_when_ready(url: str, *, timeout_seconds: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _health_ready(url):
            _open_url(url)
            return
        time.sleep(0.5)


def _open_url(url: str) -> None:
    subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f"Start-Process '{url}'",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=False,
    )


def _health_ready(url: str) -> bool:
    try:
        with urlopen(f"{url}health", timeout=1.0) as response:
            return response.status == 200
    except URLError:
        return False
    except OSError:
        return False


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0
