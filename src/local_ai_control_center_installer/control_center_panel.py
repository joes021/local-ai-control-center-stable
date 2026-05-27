from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
from urllib.error import URLError
from urllib.request import urlopen

import uvicorn

from local_ai_control_center_installer.control_center_backend.main import app
from local_ai_control_center_installer.control_center_backend.config import get_config
from local_ai_control_center_installer.control_center_backend.services.server_service import (
    ensure_runtime_ready,
)
from local_ai_control_center_installer.platform_paths import (
    build_open_url_command,
    hidden_subprocess_creationflags,
)


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

    if _health_ready_for_install_root(url, expected_install_root=args.install_root):
        if args.open_browser:
            _open_url(url)
        return 0
    if _port_in_use(args.host, args.port):
        raise RuntimeError(f"UI port {args.port} je već zauzet drugim procesom.")

    if args.open_browser:
        threading.Thread(
            target=_open_when_ready,
            args=(url,),
            daemon=True,
        ).start()
    threading.Thread(
        target=_ensure_runtime_ready_after_panel_boot,
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
        list(build_open_url_command(url)),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=hidden_subprocess_creationflags(),
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


def _health_ready_for_install_root(url: str, *, expected_install_root: str) -> bool:
    try:
        with urlopen(f"{url}health", timeout=1.0) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return False

    install_root = str(payload.get("installRoot", "") or "").strip()
    app_name = str(payload.get("app", "") or "").strip()
    status = str(payload.get("status", "") or "").strip()
    if status.lower() != "ok" or app_name != "local-ai-control-center-stable":
        return False
    if not install_root:
        return False
    return _normalized_install_root(install_root) == _normalized_install_root(expected_install_root)


def _normalized_install_root(value: str) -> str:
    return str(Path(value).expanduser().resolve()).casefold()


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def _ensure_runtime_ready_after_panel_boot() -> None:
    config = get_config()
    log_path = config.install_root / "logs" / "control-center-runtime-autostart.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    result = ensure_runtime_ready(config)
    summary = str(result.get("summary", "") or "Runtime autostart completed.")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{summary}\n")


def _module_main(argv: list[str] | None = None) -> int:
    return run_control_center_panel_entry(argv)


if __name__ == "__main__":
    raise SystemExit(_module_main())
