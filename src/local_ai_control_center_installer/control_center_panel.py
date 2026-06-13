from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser

import uvicorn

from local_ai_control_center_installer.control_center_backend.main import app
from local_ai_control_center_installer.control_center_backend.config import get_config
from local_ai_control_center_installer.control_center_backend.services.benchmark_service import (
    load_benchmark_summary,
)
from local_ai_control_center_installer.control_center_backend.services.models_service import (
    load_models_payload,
)
from local_ai_control_center_installer.control_center_backend.services.observability_service import (
    load_observability_payload,
)
from local_ai_control_center_installer.control_center_backend.services.settings_service import (
    load_settings_payload,
)
from local_ai_control_center_installer.control_center_backend.services.server_service import (
    ensure_runtime_ready,
)
from local_ai_control_center_installer.control_center_backend.services.status_service import (
    load_status_payload,
)


DEFAULT_UI_HOST = "127.0.0.1"
DEFAULT_UI_PORT = 3210
_WINDOWLESS_STD_STREAMS: list[object] = []


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
            _open_browser(url)
        return 0
    if _port_in_use(args.host, args.port):
        raise RuntimeError(f"UI port {args.port} je već zauzet drugim procesom.")

    threading.Thread(
        target=_ensure_runtime_ready_after_panel_boot,
        daemon=True,
    ).start()
    if args.open_browser:
        threading.Thread(
            target=_open_browser_when_ready,
            args=(url,),
            kwargs={"expected_install_root": args.install_root},
            daemon=True,
        ).start()

    _ensure_std_streams_for_windowless_python()
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="warning",
        use_colors=False,
    )
    return 0


def _ensure_std_streams_for_windowless_python() -> None:
    fallback_streams: list[object] = []

    if sys.stdin is None:
        stdin_stream = open(os.devnull, "r", encoding="utf-8")
        sys.stdin = stdin_stream
        fallback_streams.append(stdin_stream)

    if sys.stdout is None:
        stdout_stream = open(os.devnull, "w", encoding="utf-8")
        sys.stdout = stdout_stream
        fallback_streams.append(stdout_stream)

    if sys.stderr is None:
        stderr_stream = open(os.devnull, "w", encoding="utf-8")
        sys.stderr = stderr_stream
        fallback_streams.append(stderr_stream)

    if fallback_streams:
        _WINDOWLESS_STD_STREAMS.extend(fallback_streams)


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


def _open_browser_when_ready(
    url: str,
    *,
    expected_install_root: str,
    timeout_seconds: float = 60.0,
    poll_interval_seconds: float = 0.5,
) -> None:
    deadline = time.monotonic() + max(timeout_seconds, 0.0)
    while time.monotonic() < deadline:
        if _health_ready_for_install_root(url, expected_install_root=expected_install_root):
            _open_browser(url)
            return
        time.sleep(max(poll_interval_seconds, 0.05))


def _open_browser(url: str) -> bool:
    try:
        if webbrowser.open(url):
            return True
    except Exception:  # noqa: BLE001
        pass
    if os.name == "nt" and hasattr(os, "startfile"):
        try:
            os.startfile(url)  # type: ignore[attr-defined]
            return True
        except Exception:  # noqa: BLE001
            return False
    return False


def _ensure_runtime_ready_after_panel_boot() -> None:
    config = get_config()
    log_path = config.install_root / "logs" / "control-center-runtime-autostart.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    result = ensure_runtime_ready(config)
    summary = str(result.get("summary", "") or "Runtime autostart completed.")
    warm_failures = _warm_control_center_caches(config)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{summary}\n")
        if warm_failures:
            for failure in warm_failures:
                handle.write(f"Cache warmup warning: {failure}\n")
        else:
            handle.write("Cache warmup completed.\n")


def _warm_control_center_caches(config=None) -> list[str]:
    config = config or get_config()
    failures: list[str] = []
    warm_steps = (
        ("status", lambda: load_status_payload(config)),
        ("settings", lambda: load_settings_payload(config, include_search_provider_status=False)),
        ("models", lambda: load_models_payload(config)),
        ("benchmark", lambda: load_benchmark_summary(config)),
        ("observability", lambda: load_observability_payload(config)),
    )
    for label, loader in warm_steps:
        try:
            loader()
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{label}: {exc}")
    return failures


def _module_main(argv: list[str] | None = None) -> int:
    return run_control_center_panel_entry(argv)


if __name__ == "__main__":
    raise SystemExit(_module_main())
