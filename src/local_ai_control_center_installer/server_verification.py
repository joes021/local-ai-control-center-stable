import inspect
import json
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from local_ai_control_center_installer.reporting import build_run_paths
from local_ai_control_center_installer.session import InstallerSession


@dataclass
class ServerVerificationTarget:
    server_executable: Path
    model_id: str
    model_path: Path
    active_model_config_path: Path


def choose_free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def launch_llama_server(
    command: list[str],
    log_path: Path,
) -> subprocess.Popen[str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("w", encoding="utf-8")
    try:
        process = subprocess.Popen(
            command,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except Exception:
        log_handle.close()
        raise

    setattr(process, "_server_log_handle", log_handle)
    return process


def probe_server_health(
    base_url: str,
    timeout_seconds: float = 1.0,
) -> str:
    return _probe_server_health(
        base_url,
        timeout_seconds=timeout_seconds,
        network_error_status="failed",
    )


def _probe_server_health_during_startup(
    base_url: str,
    timeout_seconds: float = 1.0,
) -> str:
    return _probe_server_health(
        base_url,
        timeout_seconds=timeout_seconds,
        network_error_status="loading",
    )


def _probe_server_health(
    base_url: str,
    *,
    timeout_seconds: float,
    network_error_status: str,
) -> str:
    try:
        with urlopen(f"{base_url}/health", timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 503:
            return "loading"
        return "failed"
    except (URLError, TimeoutError, OSError):
        return network_error_status
    except (ValueError, json.JSONDecodeError):
        return "failed"

    if payload.get("status") == "ok":
        return "ready"
    return "failed"


def apply_server_verification(
    session: InstallerSession,
    *,
    temp_root: Path,
    process_factory=None,
    health_probe=None,
    stop_process=None,
    select_port=None,
    now_fn=None,
    sleep_fn=None,
) -> InstallerSession:
    process_factory = process_factory or launch_llama_server
    health_probe = health_probe or _probe_server_health_during_startup
    stop_process = stop_process or stop_server_process
    select_port = select_port or choose_free_port
    now_fn = now_fn or time.monotonic
    sleep_fn = sleep_fn or time.sleep

    if (
        session.bootstrap_status != "ready"
        or session.runtime_payload_status != "ready"
    ):
        session.server_verification_status = "skipped"
        session.server_process_status = "skipped"
        session.server_health_status = "skipped"
        return session

    run_id = (session.started_at or "manual-run").replace(":", "-")
    run_paths = build_run_paths(temp_root, run_id)
    session.server_log_path = str(run_paths.server_log_path)

    try:
        target = resolve_server_verification_target(session)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        session.server_verification_status = "failed"
        session.server_process_status = "skipped"
        session.server_health_status = "skipped"
        session.failing_step = "server-verification-prerequisites"
        session.error_message = str(exc)
        return session

    try:
        session.verified_server_port = select_port("127.0.0.1")
    except OSError as exc:
        session.server_verification_status = "failed"
        session.server_process_status = "skipped"
        session.server_health_status = "skipped"
        session.failing_step = "server-port-bind"
        session.error_message = str(exc)
        return session

    session.verified_server_url = f"http://127.0.0.1:{session.verified_server_port}"
    command = _build_server_command(target, session.verified_server_port)
    verification_started_at = now_fn()

    try:
        process = process_factory(command, run_paths.server_log_path)
    except Exception as exc:
        session.server_verification_status = "failed"
        session.server_process_status = "failed"
        session.server_health_status = "skipped"
        session.failing_step = "server-process-start"
        session.error_message = str(exc)
        return session

    startup_deadline = verification_started_at + 1.0
    health_deadline = verification_started_at + 20.0
    reached_ready = False

    last_startup_time = verification_started_at

    try:
        while True:
            current_time = now_fn()
            if current_time >= startup_deadline or current_time <= last_startup_time:
                break

            if process.poll() is not None:
                session.server_verification_status = "failed"
                session.server_process_status = "failed"
                session.server_health_status = "skipped"
                session.failing_step = "server-process-start"
                return session

            last_startup_time = current_time
            sleep_fn(0.1)

        last_health_time = verification_started_at
        while True:
            current_time = now_fn()
            if current_time > health_deadline or current_time <= last_health_time:
                session.server_verification_status = "failed"
                session.server_process_status = "ready"
                session.server_health_status = "failed"
                session.failing_step = "server-health"
                return session

            if process.poll() is not None:
                session.server_verification_status = "failed"
                session.server_process_status = "failed"
                session.server_health_status = "skipped"
                session.failing_step = "server-process-start"
                return session

            remaining_health_window = max(0.0, health_deadline - current_time)
            health_status = _call_health_probe(
                health_probe,
                session.verified_server_url,
                min(1.0, remaining_health_window),
            )
            if health_status == "ready":
                session.server_process_status = "ready"
                session.server_health_status = "ready"
                session.server_verification_status = "ready"
                session.failing_step = None
                session.error_message = None
                reached_ready = True
                return session

            if health_status == "failed":
                session.server_verification_status = "failed"
                session.server_process_status = "ready"
                session.server_health_status = "failed"
                session.failing_step = "server-health"
                return session

            last_health_time = current_time
            sleep_fn(0.1)
    finally:
        cleanup_error = _cleanup_server_process(process, stop_process)
        if cleanup_error is not None:
            if session.error_message:
                session.error_message = f"{session.error_message}; {cleanup_error}"
            else:
                session.error_message = cleanup_error

            if reached_ready and session.failing_step is None:
                session.server_verification_status = "failed"
                session.server_process_status = "ready"
                session.server_health_status = "ready"
                session.failing_step = "server-process-stop"

    session.server_verification_status = "failed"
    session.server_process_status = "ready"
    session.server_health_status = "failed"
    session.failing_step = "server-health"
    return session


def resolve_server_verification_target(
    session: InstallerSession,
) -> ServerVerificationTarget:
    active_model_config_path = _require_path_string(
        session.active_model_config_path,
        "session.active_model_config_path is required",
    )
    active_model_payload = json.loads(
        active_model_config_path.read_text(encoding="utf-8")
    )
    model_id = _require_non_empty_string(
        active_model_payload.get("model_id"),
        "active model config model_id is required",
    )
    model_path = Path(
        _require_non_empty_string(
            active_model_payload.get("model_path"),
            "active model config model_path is required",
        )
    )
    if not model_path.is_file():
        raise ValueError(f"active model file does not exist: {model_path}")

    runtime_artifact_path = _require_path_string(
        session.runtime_artifact_path,
        "session.runtime_artifact_path is required",
    )
    server_executable = runtime_artifact_path / "llama-server.exe"
    if not server_executable.is_file():
        raise ValueError(f"llama-server.exe was not found at {server_executable}")

    return ServerVerificationTarget(
        server_executable=server_executable,
        model_id=model_id,
        model_path=model_path,
        active_model_config_path=active_model_config_path,
    )


def _require_path_string(raw_path: str | None, error_message: str) -> Path:
    normalized = (raw_path or "").strip()
    if not normalized:
        raise ValueError(error_message)
    return Path(normalized)


def _require_non_empty_string(value: object, error_message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(error_message)
    return value.strip()


def _build_server_command(
    target: ServerVerificationTarget,
    port: int,
) -> list[str]:
    return [
        str(target.server_executable),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--model",
        str(target.model_path),
    ]


def stop_server_process(
    process,
    *,
    now_fn=time.monotonic,
    sleep_fn=time.sleep,
    timeout_seconds: float = 5.0,
) -> bool:
    process.terminate()
    deadline = now_fn() + timeout_seconds
    while now_fn() < deadline:
        if process.poll() is not None:
            return True
        sleep_fn(0.1)
    process.kill()
    return False


def _cleanup_server_process(process, stop_process) -> str | None:
    try:
        if stop_process(process):
            return None
        return "failed to stop server verification process"
    except Exception as exc:
        return f"failed to stop server verification process: {exc}"


def _call_health_probe(
    health_probe,
    base_url: str,
    timeout_seconds: float,
) -> str:
    if "timeout_seconds" in inspect.signature(health_probe).parameters:
        return health_probe(base_url, timeout_seconds=timeout_seconds)
    return health_probe(base_url)
