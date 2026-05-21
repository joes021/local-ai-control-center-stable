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


def probe_server_health(base_url: str) -> str:
    try:
        with urlopen(f"{base_url}/health") as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 503:
            return "loading"
        return "failed"
    except (URLError, OSError, ValueError, json.JSONDecodeError):
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
    health_probe = health_probe or probe_server_health
    stop_process = stop_process or _stop_server_process
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

    session.verified_server_port = select_port("127.0.0.1")
    session.verified_server_url = f"http://127.0.0.1:{session.verified_server_port}"
    command = _build_server_command(target, session.verified_server_port)

    try:
        process = process_factory(command, run_paths.server_log_path)
    except Exception as exc:
        session.server_verification_status = "failed"
        session.server_process_status = "failed"
        session.server_health_status = "skipped"
        session.failing_step = "server-process-start"
        session.error_message = str(exc)
        return session

    startup_deadline = now_fn() + 1.0
    while True:
        if process.poll() is not None:
            session.server_verification_status = "failed"
            session.server_process_status = "failed"
            session.server_health_status = "skipped"
            session.failing_step = "server-process-start"
            return session
        if now_fn() >= startup_deadline:
            break
        sleep_fn(0.1)

    health_deadline = now_fn() + 30.0
    while now_fn() <= health_deadline:
        if process.poll() is not None:
            session.server_verification_status = "failed"
            session.server_process_status = "failed"
            session.server_health_status = "failed"
            session.failing_step = "server-health-check"
            return session

        health_status = health_probe(session.verified_server_url)
        if health_status == "ready":
            stop_process(process)
            session.server_process_status = "ready"
            session.server_health_status = "ready"
            session.server_verification_status = "ready"
            session.failing_step = None
            session.error_message = None
            return session
        if health_status == "failed":
            session.server_verification_status = "failed"
            session.server_process_status = "ready"
            session.server_health_status = "failed"
            session.failing_step = "server-health-check"
            return session
        sleep_fn(0.1)

    session.server_verification_status = "failed"
    session.server_process_status = "ready"
    session.server_health_status = "failed"
    session.failing_step = "server-health-check"
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


def _stop_server_process(process: subprocess.Popen[str]) -> bool:
    try:
        process.terminate()
        return True
    except OSError:
        try:
            process.kill()
            return True
        except OSError:
            return False
