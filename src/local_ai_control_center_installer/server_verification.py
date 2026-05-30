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
from local_ai_control_center_installer.runtime_bootstrap import (
    load_runtime_endpoint_config,
)
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


def is_loopback_port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def is_managed_runtime_port_owned_by_installation(
    port: int,
    server_executable: Path,
    install_root: Path,
) -> bool:
    listener_pid = _find_listening_pid_on_loopback_port(port)
    if listener_pid is None:
        return False

    executable_path, _ = _load_process_details(listener_pid)
    if not executable_path:
        return False

    try:
        actual_executable = Path(executable_path).expanduser().resolve()
        expected_executable = server_executable.expanduser().resolve()
        expected_root = install_root.expanduser().resolve()
    except OSError:
        return False

    try:
        actual_relative_path = actual_executable.relative_to(expected_root)
    except ValueError:
        return False

    if actual_executable == expected_executable:
        return True

    return _is_known_managed_runtime_relative_path(
        actual_relative_path,
        expected_executable_name=expected_executable.name,
    )


def _is_known_managed_runtime_relative_path(
    relative_path: Path,
    *,
    expected_executable_name: str,
) -> bool:
    parts = [part.strip().lower() for part in relative_path.parts if part.strip()]
    if not parts:
        return False

    if parts[-1] != expected_executable_name.strip().lower():
        return False

    if len(parts) >= 3 and parts[:2] == ["runtime", "llama.cpp"]:
        return True

    if len(parts) >= 4 and parts[:2] == ["tools", "turboquant"]:
        return True

    return False


def stop_managed_runtime_on_port(
    port: int,
    server_executable: Path,
    install_root: Path,
    *,
    now_fn=time.monotonic,
    sleep_fn=time.sleep,
    timeout_seconds: float = 5.0,
) -> bool:
    if not is_managed_runtime_port_owned_by_installation(
        port,
        server_executable,
        install_root,
    ):
        return False

    listener_pid = _find_listening_pid_on_loopback_port(port)
    if listener_pid is None:
        return False

    command = f"Stop-Process -Id {listener_pid} -Force -ErrorAction Stop"
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
    )

    deadline = now_fn() + timeout_seconds
    while now_fn() < deadline:
        if _find_listening_pid_on_loopback_port(port) is None:
            return True
        sleep_fn(0.1)

    if _find_listening_pid_on_loopback_port(port) is None:
        return True

    return result.returncode == 0


def _find_listening_pid_on_loopback_port(port: int) -> int | None:
    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None

    expected_local_address = f"127.0.0.1:{port}".lower()
    for raw_line in result.stdout.splitlines():
        columns = raw_line.split()
        if len(columns) < 5 or columns[0].upper() != "TCP":
            continue

        local_address = columns[1].lower()
        state = columns[3].upper()
        pid_raw = columns[4]
        if local_address != expected_local_address or state != "LISTENING":
            continue
        try:
            return int(pid_raw)
        except ValueError:
            return None

    return None


def _load_process_details(pid: int) -> tuple[str | None, str | None]:
    command = (
        f"$process = Get-CimInstance Win32_Process -Filter \"ProcessId = {pid}\" "
        "| Select-Object -First 1 ProcessId, ExecutablePath, CommandLine; "
        "if ($null -eq $process) { exit 1 } "
        "else { $process | ConvertTo-Json -Compress }"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None, None

    stdout = result.stdout.strip()
    if not stdout:
        return None, None

    try:
        payload = json.loads(stdout)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None, None

    if not isinstance(payload, dict):
        return None, None

    executable_path = payload.get("ExecutablePath")
    command_line = payload.get("CommandLine")
    if not isinstance(executable_path, str) or not executable_path.strip():
        executable_path = None
    if not isinstance(command_line, str) or not command_line.strip():
        command_line = None
    return executable_path, command_line


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
    port_is_free=None,
    is_managed_runtime_port_owned_by_installation=None,
    stop_managed_runtime_on_port=None,
    reuse_existing_managed_runtime: bool = True,
    now_fn=None,
    sleep_fn=None,
) -> InstallerSession:
    process_factory = process_factory or launch_llama_server
    health_probe = health_probe or _probe_server_health_during_startup
    stop_process = stop_process or stop_server_process
    port_is_free = port_is_free or is_loopback_port_free
    managed_port_owner_check = (
        is_managed_runtime_port_owned_by_installation
        or globals()["is_managed_runtime_port_owned_by_installation"]
    )
    stop_managed_runtime_owner = (
        stop_managed_runtime_on_port or globals()["stop_managed_runtime_on_port"]
    )
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
    session.server_log_path = None

    try:
        target = resolve_server_verification_target(session)
        runtime_endpoint = load_runtime_endpoint_config(
            session.runtime_endpoint_config_path
        )
    except (ValueError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        session.server_verification_status = "failed"
        session.server_process_status = "skipped"
        session.server_health_status = "skipped"
        session.failing_step = "server-verification-prerequisites"
        session.error_message = str(exc)
        return session

    install_root = Path(session.install_root).expanduser().resolve()
    managed_port = runtime_endpoint.port
    session.verified_server_port = managed_port
    session.verified_server_url = runtime_endpoint.base_url

    if not port_is_free("127.0.0.1", managed_port):
        if not managed_port_owner_check(
            managed_port,
            target.server_executable,
            install_root,
        ):
            session.server_verification_status = "failed"
            session.server_process_status = "skipped"
            session.server_health_status = "skipped"
            session.failing_step = "server-port-bind"
            session.error_message = (
                f"Managed runtime port {managed_port} is occupied by another process."
            )
            return session

        if reuse_existing_managed_runtime:
            return _verify_existing_managed_runtime(
                session,
                health_probe=health_probe,
                verification_started_at=now_fn(),
                now_fn=now_fn,
                sleep_fn=sleep_fn,
            )

        if not stop_managed_runtime_owner(
            managed_port,
            target.server_executable,
            install_root,
        ):
            session.server_verification_status = "failed"
            session.server_process_status = "skipped"
            session.server_health_status = "skipped"
            session.failing_step = "server-port-bind"
            session.error_message = (
                "Failed to stop the existing installer-managed runtime on the "
                f"managed port {managed_port}."
            )
            return session

    command = _build_server_command(target, session.verified_server_port)
    verification_started_at = now_fn()
    process = None
    session.server_log_path = str(run_paths.server_log_path)

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
    health_deadline = verification_started_at + 30.0
    poll_interval_seconds = 0.1
    startup_attempt_limit = int(1.0 / poll_interval_seconds) + 2
    health_attempt_limit = int(30.0 / poll_interval_seconds) + 2
    reached_ready = False

    try:
        for _ in range(startup_attempt_limit):
            if process.poll() is not None:
                session.server_verification_status = "failed"
                session.server_process_status = "failed"
                session.server_health_status = "skipped"
                session.failing_step = "server-process-start"
                return session
            if now_fn() >= startup_deadline:
                break
            sleep_fn(poll_interval_seconds)

        for _ in range(health_attempt_limit):
            current_time = now_fn()
            if current_time > health_deadline:
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

            sleep_fn(poll_interval_seconds)
    finally:
        if process is not None:
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


def _verify_existing_managed_runtime(
    session: InstallerSession,
    *,
    health_probe,
    verification_started_at: float,
    now_fn,
    sleep_fn,
) -> InstallerSession:
    health_deadline = verification_started_at + 30.0
    poll_interval_seconds = 0.1
    health_attempt_limit = int(30.0 / poll_interval_seconds) + 2

    for _ in range(health_attempt_limit):
        current_time = now_fn()
        if current_time > health_deadline:
            session.server_verification_status = "failed"
            session.server_process_status = "ready"
            session.server_health_status = "failed"
            session.failing_step = "server-health"
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
            return session

        if health_status == "failed":
            session.server_verification_status = "failed"
            session.server_process_status = "ready"
            session.server_health_status = "failed"
            session.failing_step = "server-health"
            return session

        sleep_fn(poll_interval_seconds)

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
    *,
    ctx_size: int | None = None,
    spec_type: str | None = None,
    temperature: float | None = None,
    top_k: int | None = None,
    top_p: float | None = None,
    min_p: float | None = None,
    repeat_penalty: float | None = None,
    repeat_last_n: int | None = None,
    presence_penalty: float | None = None,
    frequency_penalty: float | None = None,
    seed: int | None = None,
    flash_attn: str | None = None,
    gpu_layers: int | None = None,
    main_gpu: int | None = None,
    split_mode: str | None = None,
    batch_size: int | None = None,
    ubatch_size: int | None = None,
) -> list[str]:
    command = [
        str(target.server_executable),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--model",
        str(target.model_path),
    ]
    if isinstance(ctx_size, int) and ctx_size > 0:
        command.extend(["--ctx-size", str(ctx_size)])
    if isinstance(batch_size, int) and batch_size > 0:
        command.extend(["--batch-size", str(batch_size)])
    if isinstance(ubatch_size, int) and ubatch_size > 0:
        command.extend(["--ubatch-size", str(ubatch_size)])
    if isinstance(spec_type, str) and spec_type.strip():
        command.extend(["--spec-type", spec_type.strip()])
    if isinstance(flash_attn, str) and flash_attn.strip():
        command.extend(["--flash-attn", flash_attn.strip()])
    if isinstance(gpu_layers, int) and gpu_layers > 0:
        command.extend(["--n-gpu-layers", str(gpu_layers)])
    if isinstance(main_gpu, int) and main_gpu >= 0:
        command.extend(["--main-gpu", str(main_gpu)])
    if isinstance(split_mode, str) and split_mode.strip():
        command.extend(["--split-mode", split_mode.strip()])
    if isinstance(temperature, (int, float)):
        command.extend(["--temp", str(float(temperature))])
    if isinstance(top_k, int) and top_k >= 0:
        command.extend(["--top-k", str(top_k)])
    if isinstance(top_p, (int, float)):
        command.extend(["--top-p", str(float(top_p))])
    if isinstance(min_p, (int, float)):
        command.extend(["--min-p", str(float(min_p))])
    if isinstance(repeat_penalty, (int, float)):
        command.extend(["--repeat-penalty", str(float(repeat_penalty))])
    if isinstance(repeat_last_n, int) and repeat_last_n >= -1:
        command.extend(["--repeat-last-n", str(repeat_last_n)])
    if isinstance(presence_penalty, (int, float)):
        command.extend(["--presence-penalty", str(float(presence_penalty))])
    if isinstance(frequency_penalty, (int, float)):
        command.extend(["--frequency-penalty", str(float(frequency_penalty))])
    if isinstance(seed, int):
        command.extend(["--seed", str(seed)])
    return command


def stop_server_process(
    process,
    *,
    now_fn=time.monotonic,
    sleep_fn=time.sleep,
    timeout_seconds: float = 5.0,
) -> bool:
    try:
        process.terminate()
    except OSError:
        return False

    deadline = now_fn() + timeout_seconds
    while now_fn() < deadline:
        if process.poll() is not None:
            return True
        sleep_fn(0.1)

    try:
        process.kill()
    except OSError:
        return False

    post_kill_deadline = now_fn() + timeout_seconds
    while now_fn() < post_kill_deadline:
        if process.poll() is not None:
            return True
        sleep_fn(0.1)

    return process.poll() is not None


def _cleanup_server_process(process, stop_process) -> str | None:
    log_handle = getattr(process, "_server_log_handle", None)
    try:
        if stop_process(process):
            return None
        return "failed to stop server verification process"
    except Exception as exc:
        return f"failed to stop server verification process: {exc}"
    finally:
        if log_handle is not None:
            try:
                log_handle.close()
            except Exception:
                pass


def _call_health_probe(
    health_probe,
    base_url: str,
    timeout_seconds: float,
) -> str:
    if "timeout_seconds" in inspect.signature(health_probe).parameters:
        return health_probe(base_url, timeout_seconds=timeout_seconds)
    return health_probe(base_url)
