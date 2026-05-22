import inspect
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import mkdtemp

from local_ai_control_center_installer.opencode_bootstrap import (
    load_opencode_manifest,
)
from local_ai_control_center_installer.reporting import build_run_paths
from local_ai_control_center_installer.session import InstallerSession


@dataclass
class OpenCodeVerificationTarget:
    executable_path: Path
    managed_config_path: Path
    managed_config_text: str
    model_id: str
    model_path: Path
    verified_server_url: str
    extra_env: dict[str, str]


def apply_opencode_verification(
    session: InstallerSession,
    *,
    temp_root: Path,
    process_factory=None,
    stop_process=None,
    now_fn=None,
    sleep_fn=None,
) -> InstallerSession:
    process_factory = process_factory or launch_opencode_verification_process
    stop_process = stop_process or stop_opencode_process
    now_fn = now_fn or time.monotonic
    sleep_fn = sleep_fn or time.sleep

    if session.opencode_artifact_status != "ready":
        session.opencode_verification_status = "skipped"
        session.opencode_process_status = "skipped"
        session.opencode_connection_status = "skipped"
        return session

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

    command = _build_verification_command(target.executable_path)
    session.verified_opencode_command = " ".join(command)

    env = _build_verification_env(target)
    try:
        working_directory = _make_working_directory(run_paths.run_dir)
    except OSError as exc:
        session.opencode_verification_status = "failed"
        session.opencode_process_status = "failed"
        session.opencode_connection_status = "skipped"
        session.failing_step = "opencode-process-start"
        session.error_message = str(exc)
        return session

    try:
        process = process_factory(
            command,
            cwd=working_directory,
            env=env,
            log_path=run_paths.opencode_log_path,
        )
    except Exception as exc:
        session.opencode_verification_status = "failed"
        session.opencode_process_status = "failed"
        session.opencode_connection_status = "skipped"
        session.failing_step = "opencode-process-start"
        session.error_message = str(exc)
        return session

    handshake_succeeded = False

    try:
        stdout_text = _collect_process_output(
            process,
            run_paths.opencode_log_path,
            timeout_seconds=30.0,
        )
        _set_opencode_log_path_if_present(session, run_paths.opencode_log_path)
        if process.returncode != 0:
            session.opencode_verification_status = "failed"
            session.opencode_process_status = "failed"
            session.opencode_connection_status = "skipped"
            session.failing_step = "opencode-process-start"
            session.error_message = (
                f"OpenCode verification process exited with code {process.returncode}."
            )
            return session
        handshake_succeeded = _is_successful_handshake(
            process.returncode,
            stdout_text,
            target.model_id,
            target.managed_config_text,
            target.verified_server_url,
        )
        if handshake_succeeded:
            session.opencode_verification_status = "ready"
            session.opencode_process_status = "ready"
            session.opencode_connection_status = "ready"
            session.failing_step = None
            session.error_message = None
            session.last_successful_step = "opencode-verification"
        else:
            session.opencode_verification_status = "failed"
            session.opencode_process_status = "ready"
            session.opencode_connection_status = "failed"
            session.failing_step = "opencode-connection"
            session.error_message = "OpenCode verification handshake did not match the managed route."
    except OSError as exc:
        session.opencode_verification_status = "failed"
        session.opencode_process_status = (
            "ready" if process.returncode == 0 else "failed"
        )
        session.opencode_connection_status = (
            "failed" if process.returncode in (None, 0) else "skipped"
        )
        session.failing_step = (
            "opencode-connection"
            if process.returncode in (None, 0)
            else "opencode-process-start"
        )
        session.error_message = str(exc)
    except subprocess.TimeoutExpired as exc:
        log_write_error = _try_write_log_text(
            run_paths.opencode_log_path, _coerce_output_text(exc.output)
        )
        if log_write_error is None:
            _set_opencode_log_path_if_present(session, run_paths.opencode_log_path)
        session.opencode_verification_status = "failed"
        session.opencode_process_status = "failed"
        session.opencode_connection_status = "failed"
        session.failing_step = "opencode-connection"
        session.error_message = "OpenCode verification timed out before proving the managed route."
        if log_write_error is not None:
            session.error_message = f"{session.error_message}; {log_write_error}"
    finally:
        cleanup_error = _cleanup_opencode_process(
            process,
            stop_process,
            now_fn=now_fn,
            sleep_fn=sleep_fn,
        )
        if cleanup_error is not None:
            if session.error_message:
                session.error_message = f"{session.error_message}; {cleanup_error}"
            else:
                session.error_message = cleanup_error

            if handshake_succeeded and session.failing_step is None:
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
        managed_config_path=managed_config_path,
        managed_config_text=managed_config_text,
        model_id=model_id,
        model_path=model_path,
        verified_server_url=verified_server_url,
        extra_env=launch_contract["extra_env"],
    )


def launch_opencode_verification_process(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
):
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
) -> dict[str, str]:
    override_payload = {
        "installer_managed": True,
        "autoupdate": False,
        "model": f"local-lacc/{target.model_id}",
        "enabled_providers": ["local-lacc"],
        "providers": {
            "local-lacc": {
                "provider": "@ai-sdk/openai-compatible",
                "options": {"baseURL": f"{target.verified_server_url}/v1"},
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


def _build_verification_command(executable_path: Path) -> list[str]:
    return [str(executable_path), "--pure", "models", "local-lacc"]


def _make_working_directory(run_dir: Path) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    return Path(mkdtemp(prefix="opencode-verification-", dir=str(run_dir)))


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


def _set_opencode_log_path_if_present(
    session: InstallerSession,
    log_path: Path,
) -> None:
    if log_path.exists() and log_path.is_file():
        session.opencode_log_path = str(log_path)


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
    if verification_args != ["--pure", "models"]:
        raise ValueError(
            "OpenCode manifest verification_args must equal ['--pure', 'models']."
        )

    extra_env = launch.get("extra_env")
    if not isinstance(extra_env, dict):
        raise ValueError("OpenCode manifest extra_env must be an object.")

    for key, value in extra_env.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("OpenCode manifest extra_env entries must be strings.")

    return {
        "executable_relative_path": executable_relative_path.strip(),
        "extra_env": extra_env,
    }


def _try_write_log_text(log_path: Path, text: str) -> str | None:
    try:
        _write_log_text(log_path, text)
        return None
    except OSError as exc:
        return str(exc)


def _is_successful_handshake(
    returncode: int | None,
    stdout_text: str,
    model_id: str,
    config_text: str,
    verified_server_url: str,
) -> bool:
    expected_model_token = f"local-lacc/{model_id}"
    expected_base_url = f"{verified_server_url}/v1"
    if returncode != 0:
        return False

    stdout_tokens = stdout_text.split()
    if expected_model_token not in stdout_tokens:
        return False

    try:
        config_payload = json.loads(config_text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False

    actual_base_url = (
        config_payload.get("providers", {})
        .get("local-lacc", {})
        .get("options", {})
        .get("baseURL")
    )

    return (
        isinstance(actual_base_url, str)
        and actual_base_url == expected_base_url
    )


def _cleanup_opencode_process(
    process,
    stop_process,
    *,
    now_fn,
    sleep_fn,
    timeout_seconds: float = 5.0,
) -> str | None:
    try:
        if _cleanup_supports_kwargs(stop_process):
            stopped = stop_process(
                process,
                now_fn=now_fn,
                sleep_fn=sleep_fn,
                timeout_seconds=timeout_seconds,
            )
        else:
            stopped = stop_process(process)

        if stopped:
            return None
        return "failed to stop OpenCode verification process"
    except Exception as exc:
        return f"failed to stop OpenCode verification process: {exc}"


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
