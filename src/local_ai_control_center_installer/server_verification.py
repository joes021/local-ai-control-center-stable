import json
from dataclasses import dataclass
from pathlib import Path

from local_ai_control_center_installer.reporting import build_run_paths
from local_ai_control_center_installer.session import InstallerSession


@dataclass
class ServerVerificationTarget:
    server_executable: Path
    model_id: str
    model_path: Path
    active_model_config_path: Path


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
        resolve_server_verification_target(session)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        session.server_verification_status = "failed"
        session.server_process_status = "skipped"
        session.server_health_status = "skipped"
        session.failing_step = "server-verification-prerequisites"
        session.error_message = str(exc)
        return session

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
    if not model_path.exists():
        raise ValueError(f"active model file does not exist: {model_path}")

    runtime_artifact_path = _require_path_string(
        session.runtime_artifact_path,
        "session.runtime_artifact_path is required",
    )
    server_executable = runtime_artifact_path / "llama-server.exe"
    if not server_executable.exists():
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
