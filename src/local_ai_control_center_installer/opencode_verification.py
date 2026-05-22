import inspect
import json
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import mkdtemp
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from local_ai_control_center_installer.opencode_bootstrap import (
    load_opencode_manifest,
)
from local_ai_control_center_installer.reporting import build_run_paths
from local_ai_control_center_installer.server_verification import (
    choose_free_port,
    launch_llama_server,
)
from local_ai_control_center_installer.session import InstallerSession


@dataclass
class OpenCodeVerificationTarget:
    executable_path: Path
    runtime_executable_path: Path
    managed_config_path: Path
    managed_config_text: str
    model_id: str
    model_path: Path
    verified_server_url: str
    extra_env: dict[str, str]
    verification_args: list[str]


@dataclass
class RelayProofState:
    marker_seen: bool = False
    upstream_success: bool = False
    response_has_assistant_content: bool = False
    upstream_error: str | None = None


@dataclass
class TemporaryRuntimeHandle:
    process: object
    base_url: str
    log_path: Path


@dataclass
class VerificationRelayHandle:
    server: ThreadingHTTPServer
    base_url: str
    proof_state: RelayProofState


def apply_opencode_verification(
    session: InstallerSession,
    *,
    temp_root: Path,
    process_factory=None,
    runtime_server_factory=None,
    relay_factory=None,
    stop_process=None,
    stop_runtime=None,
    stop_relay=None,
    marker_factory=None,
    now_fn=None,
    sleep_fn=None,
) -> InstallerSession:
    process_factory = process_factory or launch_opencode_verification_process
    runtime_server_factory = runtime_server_factory or start_temporary_runtime_server
    relay_factory = relay_factory or start_verification_relay
    stop_process = stop_process or stop_opencode_process
    stop_runtime = stop_runtime or stop_temporary_runtime
    stop_relay = stop_relay or stop_verification_relay
    marker_factory = marker_factory or _default_marker_factory
    now_fn = now_fn or time.monotonic
    sleep_fn = sleep_fn or time.sleep

    session.verified_opencode_command = None

    if session.opencode_artifact_status != "ready":
        session.opencode_verification_status = "skipped"
        session.opencode_process_status = "skipped"
        session.opencode_connection_status = "skipped"
        return session

    session.opencode_log_path = None
    run_id = (session.started_at or "manual-run").replace(":", "-")
    run_paths = build_run_paths(temp_root, run_id)

    try:
        target = resolve_opencode_verification_target(session)
    except (OSError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        session.opencode_verification_status = "failed"
        session.opencode_process_status = "skipped"
        session.opencode_connection_status = "skipped"
        session.failing_step = "opencode-verification-prerequisites"
        session.error_message = str(exc)
        return session

    try:
        working_directory = _make_working_directory(run_paths.run_dir)
    except OSError as exc:
        session.opencode_verification_status = "failed"
        session.opencode_process_status = "failed"
        session.opencode_connection_status = "skipped"
        session.failing_step = "opencode-inference-smoke"
        session.error_message = str(exc)
        return session

    runtime_handle = None
    relay_handle = None
    process = None
    proof_state = RelayProofState()
    verification_succeeded = False

    try:
        runtime_handle = runtime_server_factory(
            target,
            run_paths=run_paths,
            now_fn=now_fn,
            sleep_fn=sleep_fn,
        )
    except Exception as exc:
        session.opencode_verification_status = "failed"
        session.opencode_process_status = "skipped"
        session.opencode_connection_status = "skipped"
        session.failing_step = "opencode-runtime-server-start"
        session.error_message = str(exc)
        return session

    marker = marker_factory()

    try:
        relay_handle = relay_factory(
            upstream_base_url=runtime_handle.base_url,
            marker=marker,
            now_fn=now_fn,
            sleep_fn=sleep_fn,
        )
        proof_state = relay_handle.proof_state
    except Exception as exc:
        cleanup_error = _cleanup_with_optional_clock(
            runtime_handle,
            stop_runtime,
            failure_label="failed to stop OpenCode temporary runtime",
            now_fn=now_fn,
            sleep_fn=sleep_fn,
        )
        session.opencode_verification_status = "failed"
        session.opencode_process_status = "skipped"
        session.opencode_connection_status = "skipped"
        session.failing_step = "opencode-relay-start"
        session.error_message = str(exc)
        if cleanup_error is not None:
            session.error_message = f"{session.error_message}; {cleanup_error}"
        return session

    command = _build_verification_command(
        target.executable_path,
        verification_args=target.verification_args,
        model_id=target.model_id,
        marker=marker,
    )
    session.verified_opencode_command = _format_windows_command(command)
    env = _build_verification_env(target, relay_base_url=relay_handle.base_url)

    try:
        process = process_factory(
            command,
            cwd=working_directory,
            env=env,
            log_path=run_paths.opencode_log_path,
        )
        _collect_process_output(
            process,
            run_paths.opencode_log_path,
            timeout_seconds=30.0,
        )
        _set_opencode_log_path_if_present(session, run_paths.opencode_log_path)
        verification_succeeded = _apply_process_and_proof_result(
            session,
            process_returncode=process.returncode,
            proof_state=proof_state,
        )
    except subprocess.TimeoutExpired as exc:
        log_write_error = _try_write_log_text(
            run_paths.opencode_log_path,
            _coerce_output_text(exc.output),
        )
        if log_write_error is None:
            _set_opencode_log_path_if_present(session, run_paths.opencode_log_path)
        session.opencode_verification_status = "failed"
        session.opencode_process_status = "failed"
        session.opencode_connection_status = _derive_connection_status(proof_state)
        session.failing_step = _derive_timeout_step(proof_state)
        session.error_message = "OpenCode inference smoke timed out."
        if proof_state.upstream_error:
            session.error_message = (
                f"{session.error_message}; {proof_state.upstream_error}"
            )
        if log_write_error is not None:
            session.error_message = f"{session.error_message}; {log_write_error}"
    except Exception as exc:
        session.opencode_verification_status = "failed"
        session.opencode_process_status = (
            "ready" if process is not None and process.returncode == 0 else "failed"
        )
        session.opencode_connection_status = _derive_connection_status(proof_state)
        session.failing_step = _derive_runtime_failure_step(process, proof_state)
        session.error_message = str(exc)
    finally:
        cleanup_error = _cleanup_verification_resources(
            process,
            relay_handle,
            runtime_handle,
            stop_process=stop_process,
            stop_relay=stop_relay,
            stop_runtime=stop_runtime,
            now_fn=now_fn,
            sleep_fn=sleep_fn,
        )
        if cleanup_error is not None:
            if session.error_message:
                session.error_message = f"{session.error_message}; {cleanup_error}"
            else:
                session.error_message = cleanup_error

            if verification_succeeded and session.failing_step is None:
                session.opencode_verification_status = "failed"
                session.opencode_process_status = "ready"
                session.opencode_connection_status = "ready"
                session.failing_step = "opencode-process-stop"

    return session


def resolve_opencode_verification_target(
    session: InstallerSession,
) -> OpenCodeVerificationTarget:
    verified_server_url = _require_non_empty_string(
        session.verified_server_url,
        "session.verified_server_url is required",
    )
    active_model_config_path = _require_path(
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

    runtime_artifact_root = _require_path(
        session.runtime_artifact_path,
        "session.runtime_artifact_path is required",
    )
    runtime_executable_path = runtime_artifact_root / "llama-server.exe"
    if not runtime_executable_path.is_file():
        raise ValueError(
            f"llama-server.exe was not found at {runtime_executable_path}"
        )

    artifact_root = _require_path(
        session.opencode_artifact_path,
        "session.opencode_artifact_path is required",
    )

    managed_config_path = _require_path(
        session.opencode_config_path,
        "session.opencode_config_path is required",
    )
    if not managed_config_path.is_file():
        raise ValueError(f"managed OpenCode config does not exist: {managed_config_path}")
    managed_config_text = managed_config_path.read_text(encoding="utf-8")

    launch_contract = _load_launch_contract()
    executable_path = artifact_root / launch_contract["executable_relative_path"]
    if not executable_path.is_file():
        raise ValueError(f"opencode.exe was not found at {executable_path}")

    return OpenCodeVerificationTarget(
        executable_path=executable_path,
        runtime_executable_path=runtime_executable_path,
        managed_config_path=managed_config_path,
        managed_config_text=managed_config_text,
        model_id=model_id,
        model_path=model_path,
        verified_server_url=verified_server_url,
        extra_env=launch_contract["extra_env"],
        verification_args=launch_contract["verification_args"],
    )


def start_temporary_runtime_server(
    target: OpenCodeVerificationTarget,
    *,
    run_paths,
    now_fn=time.monotonic,
    sleep_fn=time.sleep,
) -> TemporaryRuntimeHandle:
    port = choose_free_port("127.0.0.1")
    base_url = f"http://127.0.0.1:{port}"
    command = [
        str(target.runtime_executable_path),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--model",
        str(target.model_path),
    ]
    runtime_log_path = _temporary_runtime_log_path(run_paths.run_dir)
    process = _launch_temporary_runtime_process(command, runtime_log_path)
    handle = TemporaryRuntimeHandle(
        process=process,
        base_url=base_url,
        log_path=runtime_log_path,
    )

    started_at = now_fn()
    startup_deadline = started_at + 1.0
    health_deadline = started_at + 30.0
    poll_interval_seconds = 0.1
    startup_attempt_limit = int(1.0 / poll_interval_seconds) + 2
    health_attempt_limit = int(30.0 / poll_interval_seconds) + 2
    became_ready = False

    try:
        for _ in range(startup_attempt_limit):
            if process.poll() is not None:
                raise RuntimeError(
                    "temporary runtime server exited before becoming healthy"
                )
            if now_fn() >= startup_deadline:
                break
            sleep_fn(poll_interval_seconds)

        for _ in range(health_attempt_limit):
            current_time = now_fn()
            if current_time > health_deadline:
                raise RuntimeError(
                    "temporary runtime server did not become healthy before timeout"
                )
            if process.poll() is not None:
                raise RuntimeError(
                    "temporary runtime server exited before becoming healthy"
                )
            remaining_window = max(0.0, health_deadline - current_time)
            health_status = _probe_runtime_health_during_startup(
                base_url,
                timeout_seconds=min(1.0, remaining_window),
            )
            if health_status == "ready":
                became_ready = True
                return handle
            if health_status == "failed":
                raise RuntimeError("temporary runtime server reported an unhealthy state")
            sleep_fn(poll_interval_seconds)
    except Exception:
        if not became_ready:
            stop_temporary_runtime(
                handle,
                now_fn=now_fn,
                sleep_fn=sleep_fn,
            )
        raise

    raise RuntimeError("temporary runtime server did not become healthy before timeout")


def _launch_temporary_runtime_process(command: list[str], log_path: Path):
    return launch_llama_server(command, log_path)


def _probe_runtime_health_during_startup(
    base_url: str,
    timeout_seconds: float = 1.0,
) -> str:
    try:
        with urlopen(f"{base_url}/health", timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 503:
            return "loading"
        return "failed"
    except (URLError, TimeoutError, OSError):
        return "loading"
    except (ValueError, json.JSONDecodeError):
        return "failed"

    if payload.get("status") == "ok":
        return "ready"
    return "failed"


def stop_temporary_runtime(
    handle: TemporaryRuntimeHandle,
    *,
    now_fn=time.monotonic,
    sleep_fn=time.sleep,
    timeout_seconds: float = 5.0,
) -> bool:
    try:
        return stop_opencode_process(
            handle.process,
            now_fn=now_fn,
            sleep_fn=sleep_fn,
            timeout_seconds=timeout_seconds,
        )
    finally:
        _close_process_log_handle(handle.process)


def start_verification_relay(
    *,
    upstream_base_url: str,
    marker: str,
    proof_state: RelayProofState | None = None,
    host: str = "127.0.0.1",
    port: int | None = None,
    now_fn=None,
    sleep_fn=None,
) -> VerificationRelayHandle:
    del now_fn, sleep_fn
    proof_state = proof_state or RelayProofState()
    relay_port = port or choose_free_port(host)
    handler_type = _build_verification_relay_handler(
        upstream_base_url=upstream_base_url,
        marker=marker,
        proof_state=proof_state,
    )
    server = ThreadingHTTPServer((host, relay_port), handler_type)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    setattr(server, "_relay_thread", thread)
    thread.start()
    return VerificationRelayHandle(
        server=server,
        base_url=f"http://{host}:{relay_port}",
        proof_state=proof_state,
    )


def stop_verification_relay(handle: VerificationRelayHandle) -> bool:
    handle.server.shutdown()
    relay_thread = getattr(handle.server, "_relay_thread", None)
    if relay_thread is not None:
        relay_thread.join(timeout=5)
    handle.server.server_close()
    return True


def launch_opencode_verification_process(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
):
    del log_path
    return subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def stop_opencode_process(
    process,
    *,
    now_fn=time.monotonic,
    sleep_fn=time.sleep,
    timeout_seconds: float = 5.0,
) -> bool:
    if process.poll() is not None:
        return True

    try:
        process.terminate()
    except OSError:
        return process.poll() is not None

    deadline = now_fn() + timeout_seconds
    while now_fn() < deadline:
        if process.poll() is not None:
            return True
        sleep_fn(0.1)

    try:
        process.kill()
    except OSError:
        return process.poll() is not None

    post_kill_deadline = now_fn() + timeout_seconds
    while now_fn() < post_kill_deadline:
        if process.poll() is not None:
            return True
        sleep_fn(0.1)

    return process.poll() is not None


def _build_verification_relay_handler(
    *,
    upstream_base_url: str,
    marker: str,
    proof_state: RelayProofState,
):
    class VerificationRelayHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/v1/chat/completions":
                self.send_error(404, "Not Found")
                return

            content_type = self.headers.get("Content-Type", "")
            if "application/json" not in content_type.lower():
                self.send_error(415, "Expected application/json")
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            request_body = self.rfile.read(content_length)

            try:
                payload = json.loads(request_body.decode("utf-8"))
            except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
                self.send_error(400, "Invalid JSON body")
                return

            proof_state.marker_seen = proof_state.marker_seen or _messages_contain_marker(
                payload.get("messages"),
                marker,
            )

            upstream_status, upstream_headers, upstream_body = _forward_to_upstream(
                upstream_base_url=upstream_base_url,
                request_body=request_body,
            )
            _apply_upstream_proof(
                proof_state,
                upstream_status=upstream_status,
                upstream_body=upstream_body,
            )
            _write_forwarded_response(
                self,
                upstream_status=upstream_status,
                upstream_headers=upstream_headers,
                upstream_body=upstream_body,
            )

        def do_GET(self):
            self._reject_method()

        def do_DELETE(self):
            self._reject_method()

        def do_HEAD(self):
            self._reject_method()

        def do_OPTIONS(self):
            self._reject_method()

        def do_PATCH(self):
            self._reject_method()

        def do_PUT(self):
            self._reject_method()

        def log_message(self, format, *args):
            return

        def _reject_method(self):
            if self.path == "/v1/chat/completions":
                self.send_error(405, "Method Not Allowed")
                return
            self.send_error(404, "Not Found")

    return VerificationRelayHandler


def _forward_to_upstream(
    *,
    upstream_base_url: str,
    request_body: bytes,
) -> tuple[int, object, bytes]:
    request = Request(
        f"{upstream_base_url}/v1/chat/completions",
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            return response.status, response.headers, response.read()
    except HTTPError as exc:
        return exc.code, exc.headers, exc.read()
    except (URLError, TimeoutError, OSError) as exc:
        return 502, {"Content-Type": "text/plain; charset=utf-8"}, str(exc).encode(
            "utf-8"
        )


def _apply_upstream_proof(
    proof_state: RelayProofState,
    *,
    upstream_status: int,
    upstream_body: bytes,
) -> None:
    if _has_valid_live_route_proof(proof_state):
        return

    proof_state.upstream_success = False
    proof_state.response_has_assistant_content = False

    if upstream_status != 200:
        proof_state.upstream_error = f"upstream returned HTTP {upstream_status}"
        return

    try:
        payload = json.loads(upstream_body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        proof_state.upstream_error = "upstream returned invalid JSON"
        return

    if not _response_has_assistant_content(payload):
        proof_state.upstream_error = (
            "upstream returned invalid assistant payload"
        )
        return

    proof_state.upstream_success = True
    proof_state.response_has_assistant_content = True
    proof_state.upstream_error = None


def _write_forwarded_response(
    handler: BaseHTTPRequestHandler,
    *,
    upstream_status: int,
    upstream_headers,
    upstream_body: bytes,
) -> None:
    handler.send_response(upstream_status)
    content_type = None
    if hasattr(upstream_headers, "get"):
        content_type = upstream_headers.get("Content-Type")
    if content_type:
        handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(upstream_body)))
    handler.end_headers()
    if upstream_body:
        handler.wfile.write(upstream_body)


def _messages_contain_marker(messages: object, marker: str) -> bool:
    if not isinstance(messages, list):
        return False
    for message in messages:
        if not isinstance(message, dict):
            continue
        if _value_contains_marker(message.get("content"), marker):
            return True
    return False


def _value_contains_marker(value: object, marker: str) -> bool:
    if isinstance(value, str):
        return marker in value
    if isinstance(value, list):
        return any(_value_contains_marker(item, marker) for item in value)
    if isinstance(value, dict):
        if isinstance(value.get("text"), str) and marker in value["text"]:
            return True
        return any(_value_contains_marker(item, marker) for item in value.values())
    return False


def _response_has_assistant_content(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return False
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        if message.get("role") != "assistant":
            continue
        if _assistant_content_present(message.get("content")):
            return True
    return False


def _assistant_content_present(content: object) -> bool:
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    if item["text"].strip():
                        return True
                elif _assistant_content_present(item):
                    return True
            elif _assistant_content_present(item):
                return True
    if isinstance(content, dict):
        text_value = content.get("text")
        if isinstance(text_value, str) and text_value.strip():
            return True
    return False


def _apply_process_and_proof_result(
    session: InstallerSession,
    *,
    process_returncode: int | None,
    proof_state: RelayProofState,
) -> bool:
    if (
        process_returncode == 0
        and proof_state.marker_seen
        and proof_state.upstream_success
        and proof_state.response_has_assistant_content
    ):
        session.opencode_verification_status = "ready"
        session.opencode_process_status = "ready"
        session.opencode_connection_status = "ready"
        session.failing_step = None
        session.error_message = None
        session.last_successful_step = "opencode-verification"
        return True

    session.opencode_verification_status = "failed"

    if proof_state.marker_seen and (
        not proof_state.upstream_success
        or not proof_state.response_has_assistant_content
    ):
        session.opencode_process_status = (
            "ready" if process_returncode == 0 else "failed"
        )
        session.opencode_connection_status = "failed"
        session.failing_step = "opencode-live-route-proof"
        session.error_message = proof_state.upstream_error or (
            "verification relay did not receive a valid assistant response"
        )
        return False

    if process_returncode != 0:
        session.opencode_process_status = "failed"
        session.opencode_connection_status = _derive_connection_status(proof_state)
        session.failing_step = "opencode-inference-smoke"
        session.error_message = (
            f"OpenCode inference smoke exited with code {process_returncode}."
        )
        return False

    session.opencode_process_status = "ready"
    session.opencode_connection_status = "failed"
    session.failing_step = "opencode-live-route-proof"
    session.error_message = (
        "verification relay did not observe the expected marker in /v1/chat/completions"
    )
    return False


def _derive_connection_status(proof_state: RelayProofState) -> str:
    if _has_valid_live_route_proof(proof_state):
        return "ready"
    if proof_state.marker_seen:
        return "failed"
    return "skipped"


def _derive_timeout_step(proof_state: RelayProofState) -> str:
    if proof_state.marker_seen and not proof_state.upstream_success:
        return "opencode-live-route-proof"
    return "opencode-inference-smoke"


def _derive_runtime_failure_step(process, proof_state: RelayProofState) -> str:
    if process is not None and process.returncode == 0 and _has_valid_live_route_proof(
        proof_state
    ):
        return "opencode-inference-smoke"
    if proof_state.marker_seen and not proof_state.upstream_success:
        return "opencode-live-route-proof"
    if process is None or process.returncode != 0:
        return "opencode-inference-smoke"
    return "opencode-live-route-proof"


def _default_marker_factory() -> str:
    return f"LACC_VERIFY_MARKER:{uuid.uuid4()}"


def _require_path(raw_path: str | None, error_message: str) -> Path:
    normalized = (raw_path or "").strip()
    if not normalized:
        raise ValueError(error_message)
    return Path(normalized)


def _require_non_empty_string(value: object, error_message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(error_message)
    return value.strip()


def _build_verification_env(
    target: OpenCodeVerificationTarget,
    *,
    relay_base_url: str,
) -> dict[str, str]:
    override_payload = {
        "installer_managed": True,
        "autoupdate": False,
        "model": f"local-lacc/{target.model_id}",
        "enabled_providers": ["local-lacc"],
        "providers": {
            "local-lacc": {
                "provider": "@ai-sdk/openai-compatible",
                "options": {"baseURL": f"{relay_base_url}/v1"},
                "models": {target.model_id: {}},
            }
        },
    }
    env = os.environ.copy()
    env.update(target.extra_env)
    env["OPENCODE_CONFIG"] = str(target.managed_config_path)
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps(override_payload)
    env["OPENCODE_DISABLE_MODELS_FETCH"] = "true"
    return env


def _build_verification_command(
    executable_path: Path,
    *,
    verification_args: list[str],
    model_id: str,
    marker: str,
) -> list[str]:
    return [
        str(executable_path),
        *verification_args,
        f"local-lacc/{model_id}",
        f"Repeat this exact token once: {marker}",
    ]


def _make_working_directory(run_dir: Path) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    return Path(mkdtemp(prefix="opencode-verification-", dir=str(run_dir)))


def _temporary_runtime_log_path(run_dir: Path) -> Path:
    return run_dir / "opencode-runtime-server.log"


def _collect_process_output(
    process,
    log_path: Path,
    *,
    timeout_seconds: float,
) -> str:
    stdout_text, _ = process.communicate(timeout=timeout_seconds)
    text = _coerce_output_text(stdout_text)
    _write_log_text(log_path, text)
    return text


def _write_log_text(log_path: Path, text: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(text, encoding="utf-8")


def _coerce_output_text(output: object) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return str(output)


def _format_windows_command(command: list[str]) -> str:
    return subprocess.list2cmdline(command)


def _set_opencode_log_path_if_present(
    session: InstallerSession,
    log_path: Path,
) -> None:
    if log_path.exists() and log_path.is_file():
        session.opencode_log_path = str(log_path)


def _has_valid_live_route_proof(proof_state: RelayProofState) -> bool:
    return (
        proof_state.marker_seen
        and proof_state.upstream_success
        and proof_state.response_has_assistant_content
    )


def _load_launch_contract() -> dict[str, object]:
    manifest = load_opencode_manifest()
    if not isinstance(manifest, dict):
        raise ValueError("OpenCode manifest must be a JSON object.")

    artifact = manifest.get("opencode_artifact")
    if not isinstance(artifact, dict):
        raise ValueError("OpenCode manifest opencode_artifact must be an object.")

    launch = artifact.get("launch")
    if not isinstance(launch, dict):
        raise ValueError("OpenCode manifest launch contract is missing or invalid.")

    executable_relative_path = launch.get("executable_relative_path")
    if (
        not isinstance(executable_relative_path, str)
        or not executable_relative_path.strip()
    ):
        raise ValueError(
            "OpenCode manifest executable_relative_path must be a non-empty string."
        )

    verification_args = launch.get("verification_args")
    expected_args = ["--pure", "run", "--format", "json", "--model"]
    if verification_args != expected_args:
        raise ValueError(
            "OpenCode manifest verification_args must equal "
            "['--pure', 'run', '--format', 'json', '--model']."
        )

    extra_env = launch.get("extra_env")
    if not isinstance(extra_env, dict):
        raise ValueError("OpenCode manifest extra_env must be an object.")

    for key, value in extra_env.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("OpenCode manifest extra_env entries must be strings.")

    return {
        "executable_relative_path": executable_relative_path.strip(),
        "verification_args": list(verification_args),
        "extra_env": extra_env,
    }


def _try_write_log_text(log_path: Path, text: str) -> str | None:
    try:
        _write_log_text(log_path, text)
        return None
    except OSError as exc:
        return str(exc)


def _cleanup_verification_resources(
    process,
    relay_handle,
    runtime_handle,
    *,
    stop_process,
    stop_relay,
    stop_runtime,
    now_fn,
    sleep_fn,
) -> str | None:
    cleanup_errors: list[str] = []

    if process is not None:
        cleanup_error = _cleanup_with_optional_clock(
            process,
            stop_process,
            failure_label="failed to stop OpenCode verification process",
            now_fn=now_fn,
            sleep_fn=sleep_fn,
        )
        if cleanup_error is not None:
            cleanup_errors.append(cleanup_error)

    if relay_handle is not None:
        cleanup_error = _cleanup_with_optional_clock(
            relay_handle,
            stop_relay,
            failure_label="failed to stop OpenCode verification relay",
            now_fn=now_fn,
            sleep_fn=sleep_fn,
        )
        if cleanup_error is not None:
            cleanup_errors.append(cleanup_error)

    if runtime_handle is not None:
        cleanup_error = _cleanup_with_optional_clock(
            runtime_handle,
            stop_runtime,
            failure_label="failed to stop OpenCode temporary runtime",
            now_fn=now_fn,
            sleep_fn=sleep_fn,
        )
        if cleanup_error is not None:
            cleanup_errors.append(cleanup_error)

    if cleanup_errors:
        return "; ".join(cleanup_errors)
    return None


def _cleanup_with_optional_clock(
    resource,
    stop_fn,
    *,
    failure_label: str,
    now_fn,
    sleep_fn,
    timeout_seconds: float = 5.0,
) -> str | None:
    try:
        if _cleanup_supports_kwargs(stop_fn):
            stopped = stop_fn(
                resource,
                now_fn=now_fn,
                sleep_fn=sleep_fn,
                timeout_seconds=timeout_seconds,
            )
        else:
            stopped = stop_fn(resource)

        if stopped:
            return None
        return failure_label
    except Exception as exc:
        return f"{failure_label}: {exc}"


def _close_process_log_handle(process) -> None:
    log_handle = getattr(process, "_server_log_handle", None)
    if log_handle is None:
        return
    try:
        log_handle.close()
    except Exception:
        pass


def _cleanup_supports_kwargs(stop_process) -> bool:
    try:
        parameters = inspect.signature(stop_process).parameters.values()
    except (TypeError, ValueError):
        return False

    if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters):
        return True

    required_names = {"now_fn", "sleep_fn", "timeout_seconds"}
    parameter_names = {parameter.name for parameter in parameters}
    return required_names.issubset(parameter_names)
