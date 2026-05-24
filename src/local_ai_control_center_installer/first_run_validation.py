import json
import os
import subprocess
import inspect
import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import mkdtemp
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from local_ai_control_center_installer.opencode_bootstrap import (
    load_opencode_manifest,
    resolve_opencode_public_model_name,
)
from local_ai_control_center_installer.opencode_verification import (
    OPENCODE_SMOKE_TIMEOUT_SECONDS,
    RelayProofState,
    start_verification_relay,
    stop_verification_relay,
)
from local_ai_control_center_installer.reporting import build_run_paths
from local_ai_control_center_installer.runtime_bootstrap import load_runtime_endpoint_config
from local_ai_control_center_installer.server_verification import (
    is_loopback_port_free,
    is_managed_runtime_port_owned_by_installation,
    launch_llama_server,
    stop_managed_runtime_on_port,
    stop_server_process,
)
from local_ai_control_center_installer.session import InstallerSession


FIRST_RUN_PROMPT = "Reply with the single word READY."
FIRST_RUN_SMOKE_TIMEOUT_SECONDS = OPENCODE_SMOKE_TIMEOUT_SECONDS


@dataclass(frozen=True)
class FirstRunValidationTarget:
    executable_path: Path
    runtime_executable_path: Path
    managed_config_path: Path
    model_id: str
    public_model_name: str
    model_path: Path
    runtime_base_url: str
    runtime_port: int
    install_root: Path
    extra_env: dict[str, str]
    verification_args: list[str]


@dataclass
class TemporaryRuntimeHandle:
    process: object
    base_url: str
    log_path: Path


def apply_first_run_validation(
    session: InstallerSession,
    *,
    temp_root: Path,
    process_factory=None,
    runtime_server_factory=None,
    stop_process=None,
    stop_runtime=None,
    relay_factory=None,
    stop_relay=None,
    port_is_free=None,
    is_managed_runtime_port_owned_by_installation=None,
    stop_managed_runtime_on_port=None,
    reuse_existing_managed_runtime: bool = True,
    now_fn=None,
    sleep_fn=None,
) -> InstallerSession:
    process_factory = process_factory or launch_first_run_process
    runtime_server_factory = runtime_server_factory or start_first_run_runtime_server
    stop_process = stop_process or stop_first_run_process
    stop_runtime = stop_runtime or stop_temporary_runtime
    relay_factory = relay_factory or start_verification_relay
    stop_relay = stop_relay or stop_verification_relay
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
        session.install_opencode is not True
        or session.bootstrap_status != "ready"
        or session.runtime_payload_status != "ready"
        or session.server_verification_status != "ready"
        or session.opencode_artifact_status != "ready"
        or session.opencode_verification_status != "ready"
    ):
        session.first_run_status = "skipped"
        session.first_run_process_status = "skipped"
        session.first_run_connection_status = "skipped"
        session.first_run_log_path = None
        return session

    session.failing_step = None
    session.error_message = None
    session.first_run_log_path = None

    run_id = (session.started_at or "manual-run").replace(":", "-")
    run_paths = build_run_paths(temp_root, run_id)

    try:
        target = resolve_first_run_validation_target(session)
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        session.first_run_status = "failed"
        session.first_run_process_status = "skipped"
        session.first_run_connection_status = "skipped"
        session.failing_step = "first-run-prerequisites"
        session.error_message = str(exc)
        return session

    try:
        working_directory = _make_working_directory(run_paths.run_dir)
    except OSError as exc:
        session.first_run_status = "failed"
        session.first_run_process_status = "failed"
        session.first_run_connection_status = "skipped"
        session.failing_step = "first-run-opencode-smoke"
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
            port_is_free=port_is_free,
            is_managed_runtime_port_owned_by_installation=managed_port_owner_check,
            stop_managed_runtime_on_port=stop_managed_runtime_owner,
            reuse_existing_managed_runtime=reuse_existing_managed_runtime,
            now_fn=now_fn,
            sleep_fn=sleep_fn,
        )
    except Exception as exc:
        session.first_run_status = "failed"
        session.first_run_process_status = "skipped"
        session.first_run_connection_status = "skipped"
        session.failing_step = "first-run-runtime-server-start"
        session.error_message = str(exc)
        return session

    try:
        relay_base_url = (
            runtime_handle.base_url if runtime_handle is not None else target.runtime_base_url
        )
        relay_handle = relay_factory(
            upstream_base_url=relay_base_url,
            marker=FIRST_RUN_PROMPT,
            now_fn=now_fn,
            sleep_fn=sleep_fn,
        )
        proof_state = relay_handle.proof_state
    except Exception as exc:
        cleanup_error = _cleanup_first_run_resources(
            process,
            relay_handle,
            runtime_handle,
            stop_process=stop_process,
            stop_relay=stop_relay,
            stop_runtime=stop_runtime,
            now_fn=now_fn,
            sleep_fn=sleep_fn,
        )
        session.first_run_status = "failed"
        session.first_run_process_status = "skipped"
        session.first_run_connection_status = "skipped"
        session.failing_step = "first-run-relay-start"
        session.error_message = str(exc)
        if cleanup_error is not None:
            session.error_message = f"{session.error_message}; {cleanup_error}"
        return session

    command = _build_first_run_command(
        target.executable_path,
        verification_args=target.verification_args,
        public_model_name=target.public_model_name,
    )
    env = _build_first_run_env(target, relay_base_url=relay_handle.base_url)

    try:
        process = process_factory(
            command,
            cwd=working_directory,
            env=env,
            log_path=run_paths.first_run_log_path,
        )
        output_text = _collect_process_output(
            process,
            run_paths.first_run_log_path,
            timeout_seconds=FIRST_RUN_SMOKE_TIMEOUT_SECONDS,
        )
        _set_first_run_log_path_if_present(session, run_paths.first_run_log_path)
        verification_succeeded = _apply_process_output_result(
            session,
            process_returncode=process.returncode,
            output_text=output_text,
            proof_state=proof_state,
        )
    except subprocess.TimeoutExpired as exc:
        log_write_error = _try_write_log_text(
            run_paths.first_run_log_path,
            _coerce_output_text(exc.output),
        )
        if log_write_error is None:
            _set_first_run_log_path_if_present(session, run_paths.first_run_log_path)
        session.first_run_status = "failed"
        session.first_run_process_status = "failed"
        session.first_run_connection_status = "skipped"
        session.failing_step = "first-run-opencode-smoke"
        session.error_message = "First-run OpenCode smoke timed out."
        if log_write_error is not None:
            session.error_message = f"{session.error_message}; {log_write_error}"
    except Exception as exc:
        session.first_run_status = "failed"
        session.first_run_process_status = (
            "ready" if process is not None and process.returncode == 0 else "failed"
        )
        session.first_run_connection_status = (
            "failed" if session.first_run_process_status == "ready" else "skipped"
        )
        session.failing_step = "first-run-opencode-smoke"
        session.error_message = str(exc)
    finally:
        cleanup_error = _cleanup_first_run_resources(
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
                session.first_run_status = "failed"
                session.first_run_process_status = "ready"
                session.first_run_connection_status = "ready"
                session.failing_step = "first-run-process-stop"

    return session


def resolve_first_run_validation_target(
    session: InstallerSession,
) -> FirstRunValidationTarget:
    install_root = _require_path(
        session.install_root,
        "session.install_root is required",
    ).expanduser().resolve()
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

    runtime_root = _require_path(
        session.runtime_artifact_path,
        "session.runtime_artifact_path is required",
    )
    runtime_executable_path = runtime_root / "llama-server.exe"
    if not runtime_executable_path.is_file():
        raise ValueError(
            f"llama-server.exe was not found at {runtime_executable_path}"
        )

    runtime_endpoint = load_runtime_endpoint_config(
        session.runtime_endpoint_config_path
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
        raise ValueError(
            f"managed OpenCode config does not exist: {managed_config_path}"
        )
    managed_config_path.read_text(encoding="utf-8")

    launch_contract = _load_launch_contract()
    executable_path = artifact_root / launch_contract["executable_relative_path"]
    if not executable_path.is_file():
        raise ValueError(f"opencode.exe was not found at {executable_path}")

    return FirstRunValidationTarget(
        executable_path=executable_path,
        runtime_executable_path=runtime_executable_path,
        managed_config_path=managed_config_path,
        model_id=model_id,
        public_model_name=resolve_opencode_public_model_name(model_id, model_path),
        model_path=model_path,
        runtime_base_url=runtime_endpoint.base_url,
        runtime_port=runtime_endpoint.port,
        install_root=install_root,
        extra_env=launch_contract["extra_env"],
        verification_args=launch_contract["verification_args"],
    )


def start_first_run_runtime_server(
    target: FirstRunValidationTarget,
    *,
    run_paths,
    port_is_free=is_loopback_port_free,
    is_managed_runtime_port_owned_by_installation=is_managed_runtime_port_owned_by_installation,
    stop_managed_runtime_on_port=stop_managed_runtime_on_port,
    reuse_existing_managed_runtime: bool = True,
    now_fn=time.monotonic,
    sleep_fn=time.sleep,
) -> TemporaryRuntimeHandle | None:
    host = "127.0.0.1"
    port = target.runtime_port
    base_url = target.runtime_base_url

    if not port_is_free(host, port):
        if not is_managed_runtime_port_owned_by_installation(
            port,
            target.runtime_executable_path,
            target.install_root,
        ):
            raise RuntimeError(
                f"Managed runtime port {port} is occupied by another process."
            )

        if reuse_existing_managed_runtime:
            return None

        if not stop_managed_runtime_on_port(
            port,
            target.runtime_executable_path,
            target.install_root,
        ):
            raise RuntimeError(
                "Failed to stop the existing installer-managed runtime on the "
                f"managed port {port}."
            )

    runtime_log_path = _temporary_runtime_log_path(run_paths.run_dir)
    command = [
        str(target.runtime_executable_path),
        "--host",
        host,
        "--port",
        str(port),
        "--model",
        str(target.model_path),
    ]
    process = launch_llama_server(command, runtime_log_path)
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
                return handle
            if health_status == "failed":
                raise RuntimeError("temporary runtime server reported an unhealthy state")
            sleep_fn(poll_interval_seconds)
    except Exception:
        stop_temporary_runtime(
            handle,
            now_fn=now_fn,
            sleep_fn=sleep_fn,
        )
        raise

    raise RuntimeError("temporary runtime server did not become healthy before timeout")


def launch_first_run_process(
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
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def stop_first_run_process(
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


def stop_temporary_runtime(
    handle: TemporaryRuntimeHandle,
    *,
    now_fn=time.monotonic,
    sleep_fn=time.sleep,
    timeout_seconds: float = 5.0,
) -> bool:
    try:
        return stop_server_process(
            handle.process,
            now_fn=now_fn,
            sleep_fn=sleep_fn,
            timeout_seconds=timeout_seconds,
        )
    finally:
        _close_process_log_handle(handle.process)


def _build_first_run_env(
    target: FirstRunValidationTarget,
    *,
    relay_base_url: str,
) -> dict[str, str]:
    override_payload = {
        "autoupdate": False,
        "model": f"local-lacc/{target.public_model_name}",
        "enabled_providers": ["local-lacc"],
        "provider": {
            "local-lacc": {
                "npm": "@ai-sdk/openai-compatible",
                "options": {"baseURL": f"{relay_base_url}/v1"},
                "models": {
                    target.public_model_name: {"name": target.public_model_name}
                },
            }
        },
    }
    env = os.environ.copy()
    env.update(target.extra_env)
    env["OPENCODE_CONFIG"] = str(target.managed_config_path)
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps(override_payload)
    env["OPENCODE_DISABLE_MODELS_FETCH"] = "true"
    return env


def _build_first_run_command(
    executable_path: Path,
    *,
    verification_args: list[str],
    public_model_name: str,
) -> list[str]:
    return [
        str(executable_path),
        *verification_args,
        f"local-lacc/{public_model_name}",
        FIRST_RUN_PROMPT,
    ]


def _apply_process_output_result(
    session: InstallerSession,
    *,
    process_returncode: int | None,
    output_text: str,
    proof_state: RelayProofState | None = None,
) -> bool:
    if process_returncode != 0:
        session.first_run_status = "failed"
        session.first_run_process_status = "failed"
        session.first_run_connection_status = "skipped"
        session.failing_step = "first-run-opencode-smoke"
        session.error_message = (
            f"First-run OpenCode smoke exited with code {process_returncode}."
        )
        return False

    response_payload = _parse_json_output(output_text)
    assistant_text = _extract_first_nonempty_assistant_text(response_payload)
    if assistant_text is None and not _has_valid_first_run_live_route_proof(proof_state):
        session.first_run_status = "failed"
        session.first_run_process_status = "ready"
        session.first_run_connection_status = "failed"
        session.failing_step = "first-run-opencode-smoke"
        session.error_message = (
            "First-run OpenCode smoke did not return a non-empty assistant response."
        )
        return False

    session.first_run_status = "ready"
    session.first_run_process_status = "ready"
    session.first_run_connection_status = "ready"
    session.failing_step = None
    session.error_message = None
    session.last_successful_step = "first-run-validation"
    return True


def _parse_json_output(output_text: str) -> object | None:
    normalized = output_text.strip()
    if not normalized:
        return None

    try:
        return json.loads(normalized)
    except (TypeError, ValueError, json.JSONDecodeError):
        pass

    line_payloads: list[object] = []
    for line in reversed(normalized.splitlines()):
        candidate = line.strip()
        if not candidate:
            continue
        try:
            line_payloads.append(json.loads(candidate))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue

    if not line_payloads:
        return None

    line_payloads.reverse()
    if len(line_payloads) == 1:
        return line_payloads[0]
    return line_payloads


def _extract_first_nonempty_assistant_text(payload: object) -> str | None:
    if isinstance(payload, list):
        for item in payload:
            text = _extract_nonempty_text_event(item)
            if text is not None:
                return text
        return None

    if not isinstance(payload, dict):
        return None
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return None

    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        text = _coerce_assistant_content(message.get("content"))
        if text is not None:
            return text
    return None


def _extract_nonempty_text_event(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None

    part = payload.get("part")
    if isinstance(part, dict):
        if part.get("type") == "text":
            text = _coerce_assistant_content(part.get("text"))
            if text is not None:
                return text

    if payload.get("type") == "text":
        text = _coerce_assistant_content(payload.get("text"))
        if text is not None:
            return text

    return None


def _coerce_assistant_content(content: object) -> str | None:
    if isinstance(content, str):
        stripped = content.strip()
        return stripped or None
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            text = _coerce_assistant_content(item)
            if text:
                parts.append(text)
        joined = " ".join(parts).strip()
        return joined or None
    if isinstance(content, dict):
        if content.get("type") == "text" and isinstance(content.get("text"), str):
            stripped = content["text"].strip()
            return stripped or None
        text_value = content.get("text")
        if isinstance(text_value, str):
            stripped = text_value.strip()
            return stripped or None
    return None


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


def _cleanup_first_run_resources(
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
            failure_label="failed to stop first-run OpenCode process",
            now_fn=now_fn,
            sleep_fn=sleep_fn,
        )
        if cleanup_error is not None:
            cleanup_errors.append(cleanup_error)

    if relay_handle is not None:
        cleanup_error = _cleanup_with_optional_clock(
            relay_handle,
            stop_relay,
            failure_label="failed to stop first-run verification relay",
            now_fn=now_fn,
            sleep_fn=sleep_fn,
        )
        if cleanup_error is not None:
            cleanup_errors.append(cleanup_error)

    if runtime_handle is not None:
        cleanup_error = _cleanup_with_optional_clock(
            runtime_handle,
            stop_runtime,
            failure_label="failed to stop first-run runtime process",
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


def _cleanup_supports_kwargs(stop_fn) -> bool:
    try:
        parameters = list(inspect.signature(stop_fn).parameters.values())
    except (TypeError, ValueError):
        return False

    if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters):
        return True

    parameter_names = {parameter.name for parameter in parameters}
    return {"now_fn", "sleep_fn", "timeout_seconds"}.issubset(parameter_names)


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


def _temporary_runtime_log_path(run_dir: Path) -> Path:
    return run_dir / "first-run-runtime-server.log"


def _make_working_directory(run_dir: Path) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    return Path(mkdtemp(prefix="first-run-validation-", dir=str(run_dir)))


def _write_log_text(log_path: Path, text: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(text, encoding="utf-8")


def _try_write_log_text(log_path: Path, text: str) -> str | None:
    try:
        _write_log_text(log_path, text)
        return None
    except OSError as exc:
        return str(exc)


def _coerce_output_text(output: object) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return str(output)


def _set_first_run_log_path_if_present(
    session: InstallerSession,
    log_path: Path,
) -> None:
    if log_path.exists() and log_path.is_file():
        session.first_run_log_path = str(log_path)


def _close_process_log_handle(process) -> None:
    log_handle = getattr(process, "_server_log_handle", None)
    if log_handle is None:
        return
    try:
        log_handle.close()
    except Exception:
        pass


def _has_valid_first_run_live_route_proof(
    proof_state: RelayProofState | None,
) -> bool:
    if proof_state is None:
        return False
    return (
        proof_state.marker_seen
        and proof_state.upstream_success
        and proof_state.response_has_assistant_content
    )


def _require_path(raw_path: str | None, error_message: str) -> Path:
    normalized = (raw_path or "").strip()
    if not normalized:
        raise ValueError(error_message)
    return Path(normalized)


def _require_non_empty_string(value: object, error_message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(error_message)
    return value.strip()
