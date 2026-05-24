import json
from importlib.resources import files
from json import JSONDecodeError
from pathlib import Path
from tempfile import mkdtemp
import inspect

from .downloads import (
    download_file as shared_download_file,
    extract_archive,
    promote_tree,
    verify_required_file_checksums,
    verify_required_files,
    verify_runtime_metadata,
    verify_sha256,
    write_runtime_metadata,
)
from .download_plan import (
    OPENCODE_ARTIFACT_DOWNLOAD_KEY,
    find_download_plan_item,
)
from .runtime_bootstrap import load_runtime_endpoint_config
from .session import InstallerSession


def load_opencode_manifest(manifest_path=None) -> dict:
    if manifest_path is None:
        manifest_path = files("local_ai_control_center_installer.manifests").joinpath(
            "windows-stable-opencode.json"
        )

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("OpenCode manifest top-level object must be a JSON object.")
    if "opencode_artifact" not in payload:
        raise ValueError("OpenCode manifest is missing required top-level fields.")

    _validate_opencode_artifact(payload["opencode_artifact"])
    return payload


def apply_opencode_bootstrap(
    session: InstallerSession,
    *,
    temp_root: Path,
    load_manifest=load_opencode_manifest,
    download_archive=None,
    extract_archive=extract_archive,
    verify_archive_sha256=verify_sha256,
    verify_required_file_checksums=verify_required_file_checksums,
    write_managed_config=None,
) -> InstallerSession:
    if session.server_verification_status != "ready":
        session.opencode_artifact_status = "skipped"
        session.opencode_verification_status = "skipped"
        session.opencode_process_status = "skipped"
        session.opencode_connection_status = "skipped"
        return session

    if not session.install_opencode:
        session.opencode_artifact_status = "skipped"
        session.opencode_verification_status = "skipped"
        session.opencode_process_status = "skipped"
        session.opencode_connection_status = "skipped"
        return session

    session.failing_step = None
    session.error_message = None

    install_root = Path(session.install_root).expanduser().resolve()
    session.install_root = str(install_root)

    try:
        manifest = load_manifest()
    except (OSError, ValueError) as exc:
        session.opencode_artifact_status = "failed"
        session.opencode_verification_status = "skipped"
        session.opencode_process_status = "skipped"
        session.opencode_connection_status = "skipped"
        session.failing_step = "opencode-manifest"
        session.error_message = str(exc)
        return session

    opencode_artifact = manifest["opencode_artifact"]
    opencode_root = install_root / opencode_artifact["install_subdir"]
    metadata_path = opencode_root / "opencode-artifact.json"
    config_path = install_root / "config" / "opencode" / "managed-config.json"

    session.opencode_artifact_id = opencode_artifact["id"]
    session.opencode_artifact_path = str(opencode_root)
    session.opencode_metadata_path = str(metadata_path)
    session.opencode_config_path = str(config_path)

    artifact_ready = _opencode_artifact_ready(
        opencode_root,
        metadata_path,
        opencode_artifact,
        verify_required_file_checksums=verify_required_file_checksums,
    )

    model_id, public_model_name = _resolve_active_model_reference(
        session.active_model_config_path
    )
    try:
        runtime_endpoint = load_runtime_endpoint_config(
            session.runtime_endpoint_config_path
        )
    except (OSError, UnicodeDecodeError, ValueError, JSONDecodeError):
        runtime_endpoint = None
    if runtime_endpoint is None or model_id is None or public_model_name is None:
        session.opencode_artifact_status = "ready" if artifact_ready else "skipped"
        if artifact_ready:
            session.last_successful_step = "opencode-artifact"
        session.opencode_verification_status = "failed"
        session.opencode_process_status = "skipped"
        session.opencode_connection_status = "skipped"
        session.failing_step = "opencode-verification-prerequisites"
        session.error_message = "OpenCode bootstrap prerequisites are missing or invalid."
        return session

    if not artifact_ready:
        plan_item = _require_download_plan_item(
            session,
            OPENCODE_ARTIFACT_DOWNLOAD_KEY,
        )
        if download_archive is None:
            download_archive = _download_file
        try:
            _stage_opencode_artifact(
                install_root=install_root,
                temp_root=temp_root,
                opencode_artifact=opencode_artifact,
                download_archive=download_archive,
                extract_archive=extract_archive,
                verify_archive_sha256=verify_archive_sha256,
                verify_required_file_checksums=verify_required_file_checksums,
                plan_item=plan_item,
            )
        except Exception as exc:
            session.opencode_artifact_status = "failed"
            session.opencode_verification_status = "skipped"
            session.opencode_process_status = "skipped"
            session.opencode_connection_status = "skipped"
            session.failing_step = "opencode-artifact"
            session.error_message = str(exc)
            return session

    session.opencode_artifact_status = "ready"
    session.last_successful_step = "opencode-artifact"
    if write_managed_config is None:
        write_managed_config = _write_managed_config

    try:
        write_managed_config(
            config_path,
            model_id=model_id,
            public_model_name=public_model_name,
            base_url=runtime_endpoint.base_url,
        )
    except Exception as exc:
        session.opencode_artifact_status = "ready"
        session.opencode_verification_status = "failed"
        session.opencode_process_status = "skipped"
        session.opencode_connection_status = "skipped"
        session.failing_step = "opencode-config"
        session.error_message = str(exc)
        return session

    session.opencode_verification_status = "skipped"
    session.opencode_process_status = "skipped"
    session.opencode_connection_status = "skipped"
    session.last_successful_step = "opencode-config"
    session.error_message = None
    return session


def _validate_opencode_artifact(opencode_artifact: dict) -> None:
    if not isinstance(opencode_artifact, dict):
        raise ValueError("OpenCode artifact entry must be an object.")

    for key in ("id", "url", "sha256", "archive_type", "install_subdir"):
        _validate_manifest_string_field(
            opencode_artifact,
            key,
            context="OpenCode artifact entry",
        )

    required_files = opencode_artifact.get("required_files")
    if not isinstance(required_files, list) or not required_files:
        raise ValueError(
            "OpenCode artifact entry required_files must be a non-empty list."
        )
    for relative_path in required_files:
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise ValueError(
                "OpenCode artifact entry required_files must contain non-empty string paths."
            )

    required_file_sha256 = opencode_artifact.get("required_file_sha256")
    if not isinstance(required_file_sha256, dict):
        raise ValueError(
            "OpenCode artifact entry required_file_sha256 must be an object."
        )
    for relative_path, checksum in required_file_sha256.items():
        if relative_path not in required_files:
            raise ValueError(
                "OpenCode artifact entry required_file_sha256 contains an unknown required file."
            )
        if not isinstance(checksum, str) or not checksum.strip():
            raise ValueError(
                f"OpenCode artifact entry required_file_sha256 has invalid value for: {relative_path}"
            )

    launch = opencode_artifact.get("launch")
    if not isinstance(launch, dict):
        raise ValueError("OpenCode artifact entry launch must be an object.")
    _validate_manifest_string_field(
        launch,
        "executable_relative_path",
        context="OpenCode artifact launch entry",
    )
    executable_relative_path = launch["executable_relative_path"]
    if executable_relative_path not in required_files:
        raise ValueError(
            "OpenCode artifact launch entry executable_relative_path must be listed in required_files."
        )

    verification_args = launch.get("verification_args")
    if verification_args != ["--pure", "run", "--format", "json", "--model"]:
        raise ValueError(
            "OpenCode artifact launch entry verification_args must equal "
            "['--pure', 'run', '--format', 'json', '--model']."
        )

    extra_env = launch.get("extra_env")
    if not isinstance(extra_env, dict):
        raise ValueError("OpenCode artifact launch entry extra_env must be an object.")


def _validate_manifest_string_field(
    payload: dict,
    key: str,
    *,
    context: str,
) -> None:
    if key not in payload:
        raise ValueError(f"{context} is missing required field: {key}")

    value = payload[key]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} field must be a non-empty string: {key}")


def _opencode_artifact_ready(
    opencode_root: Path,
    metadata_path: Path,
    opencode_artifact: dict,
    *,
    verify_required_file_checksums,
) -> bool:
    return verify_required_files(
        opencode_root, opencode_artifact["required_files"]
    ) and verify_required_file_checksums(
        opencode_root, opencode_artifact["required_file_sha256"]
    ) and verify_runtime_metadata(
        metadata_path,
        artifact_id=opencode_artifact["id"],
        source_sha256=opencode_artifact["sha256"],
    )


def _resolve_active_model_reference(
    active_model_config_path: str | None,
) -> tuple[str | None, str | None]:
    if not isinstance(active_model_config_path, str) or not active_model_config_path.strip():
        return None, None

    try:
        payload = json.loads(
            Path(active_model_config_path).read_text(encoding="utf-8")
        )
    except (JSONDecodeError, OSError, UnicodeDecodeError):
        return None, None

    if not isinstance(payload, dict):
        return None, None

    model_id = payload.get("model_id")
    if not isinstance(model_id, str) or not model_id.strip():
        return None, None
    resolved_model_id = model_id.strip()
    public_model_name = resolve_opencode_public_model_name(
        resolved_model_id,
        payload.get("model_path"),
    )
    return resolved_model_id, public_model_name


def _stage_opencode_artifact(
    *,
    install_root: Path,
    temp_root: Path,
    opencode_artifact: dict,
    download_archive,
    extract_archive,
    verify_archive_sha256,
    verify_required_file_checksums,
    plan_item,
) -> None:
    staging_root = _make_staging_root(temp_root)
    archive_path = staging_root / "downloads" / "opencode-artifact.archive"
    extracted_root = staging_root / "payload" / opencode_artifact["install_subdir"]

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    _invoke_download(
        download_archive,
        opencode_artifact["url"],
        archive_path,
        plan_item=plan_item,
    )
    if not verify_archive_sha256(archive_path, opencode_artifact["sha256"]):
        raise ValueError("OpenCode archive checksum verification failed.")

    extract_archive(
        archive_path,
        extracted_root,
        archive_type=opencode_artifact["archive_type"],
    )
    if not verify_required_files(extracted_root, opencode_artifact["required_files"]):
        raise ValueError("OpenCode artifact is missing required files.")
    if not verify_required_file_checksums(
        extracted_root, opencode_artifact["required_file_sha256"]
    ):
        raise ValueError("OpenCode artifact required file checksum verification failed.")

    write_runtime_metadata(
        extracted_root / "opencode-artifact.json",
        artifact_id=opencode_artifact["id"],
        source_sha256=opencode_artifact["sha256"],
    )
    promote_tree(staging_root / "payload", install_root)


def _write_managed_config(
    config_path: Path,
    *,
    model_id: str,
    public_model_name: str,
    base_url: str,
) -> Path:
    del model_id
    resolved_public_model_name = public_model_name.strip() or "unknown-model"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "autoupdate": False,
                "model": f"local-lacc/{resolved_public_model_name}",
                "enabled_providers": ["local-lacc", "opencode"],
                "provider": {
                    "local-lacc": {
                        "npm": "@ai-sdk/openai-compatible",
                        "options": {"baseURL": f"{base_url}/v1"},
                        "models": {
                            resolved_public_model_name: {
                                "name": resolved_public_model_name
                            }
                        },
                    }
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return config_path


def resolve_opencode_public_model_name(
    model_id: str,
    model_path: str | Path | object | None,
) -> str:
    candidate_path = ""
    if isinstance(model_path, Path):
        candidate_path = str(model_path)
    elif isinstance(model_path, str):
        candidate_path = model_path

    candidate_name = Path(candidate_path).name.strip() if candidate_path.strip() else ""
    return candidate_name or model_id.strip()


def _make_staging_root(temp_root: Path) -> Path:
    temp_root.mkdir(parents=True, exist_ok=True)
    return Path(mkdtemp(prefix="opencode-payload-", dir=str(temp_root)))


def _download_file(
    url: str,
    destination: Path,
    *,
    progress_callback=None,
    plan_item=None,
) -> Path:
    return shared_download_file(
        url,
        destination,
        progress_callback=progress_callback,
        plan_item=plan_item,
    )


def _require_download_plan_item(session: InstallerSession, key: str):
    plan_item = find_download_plan_item(session.download_plan, key)
    if plan_item is None:
        raise ValueError(f"Installer session download plan is missing item: {key}")
    return plan_item


def _invoke_download(download_func, url: str, destination: Path, *, plan_item) -> Path:
    parameters = inspect.signature(download_func).parameters.values()
    if any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters):
        return download_func(url, destination, plan_item=plan_item)
    if "plan_item" in inspect.signature(download_func).parameters:
        return download_func(url, destination, plan_item=plan_item)
    return download_func(url, destination)
