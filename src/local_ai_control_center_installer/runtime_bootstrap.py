import json
import os
from pathlib import Path
from tempfile import mkdtemp, mkstemp
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
    RUNTIME_ARTIFACT_DOWNLOAD_KEY,
    find_download_plan_item,
    starter_model_download_key,
)
from .runtime_manifest import load_runtime_manifest, resolve_requested_starter_model
from .session import InstallerSession

DEFAULT_MANAGED_RUNTIME_PORT = 39281


def apply_runtime_payload(
    session: InstallerSession,
    *,
    temp_root: Path,
    load_manifest=load_runtime_manifest,
    download_runtime_archive=None,
    download_model_file=None,
    extract_archive=extract_archive,
    verify_archive_sha256=verify_sha256,
    verify_model_file=verify_sha256,
    write_active_model_config=None,
    write_model_locations_config=None,
    write_runtime_endpoint_config=None,
    managed_runtime_port: int = DEFAULT_MANAGED_RUNTIME_PORT,
) -> InstallerSession:
    if session.bootstrap_status != "ready":
        session.runtime_payload_status = "skipped"
        session.runtime_artifact_status = "skipped"
        session.starter_model_status = "skipped"
        session.active_model_config_status = "skipped"
        session.model_locations_config_status = "skipped"
        session.runtime_endpoint_config_status = "skipped"
        return session

    session.failing_step = None
    session.last_successful_step = None
    session.error_message = None

    install_root = Path(session.install_root).expanduser().resolve()
    session.install_root = str(install_root)
    try:
        manifest = load_manifest()
    except ValueError as exc:
        session.runtime_payload_status = "failed"
        session.runtime_artifact_status = "failed"
        session.starter_model_status = "failed"
        session.active_model_config_status = "skipped"
        session.model_locations_config_status = "skipped"
        session.runtime_endpoint_config_status = "skipped"
        session.failing_step = "runtime-manifest"
        session.error_message = str(exc)
        return session
    runtime_artifact = manifest["runtime_artifact"]
    try:
        starter_model = resolve_requested_starter_model(manifest, session.starter_model)
    except ValueError as exc:
        session.runtime_payload_status = "failed"
        session.runtime_artifact_status = "skipped"
        session.starter_model_status = "failed"
        session.active_model_config_status = "skipped"
        session.model_locations_config_status = "skipped"
        session.runtime_endpoint_config_status = "skipped"
        session.failing_step = "runtime-manifest"
        session.error_message = str(exc)
        return session

    runtime_root = install_root / runtime_artifact["install_subdir"]
    runtime_metadata_path = runtime_root / "runtime-artifact.json"
    model_root = install_root / starter_model["install_subdir"]
    starter_model_path = model_root / starter_model["target_filename"]
    active_model_config_path = install_root / "config" / "active-model.json"
    model_locations_config_path = install_root / "config" / "model-locations.json"
    runtime_endpoint_config_path = install_root / "config" / "runtime-endpoint.json"

    session.runtime_artifact_id = runtime_artifact["id"]
    session.runtime_artifact_path = str(runtime_root)
    session.runtime_metadata_path = str(runtime_metadata_path)
    session.starter_model_path = str(starter_model_path)
    session.active_model_config_path = str(active_model_config_path)
    session.model_locations_config_path = str(model_locations_config_path)
    session.runtime_endpoint_config_path = str(runtime_endpoint_config_path)
    normalized_additional_paths = _normalize_additional_model_paths(
        session.additional_model_paths
    )
    session.additional_model_paths = normalized_additional_paths
    try:
        validated_managed_runtime_port = _validate_managed_runtime_port(
            managed_runtime_port
        )
    except ValueError as exc:
        session.runtime_payload_status = "failed"
        session.runtime_artifact_status = "skipped"
        session.starter_model_status = "skipped"
        session.active_model_config_status = "skipped"
        session.model_locations_config_status = "skipped"
        session.runtime_endpoint_config_status = "failed"
        session.managed_runtime_port = None
        session.failing_step = "runtime-endpoint-config"
        session.error_message = str(exc)
        return session
    session.managed_runtime_port = validated_managed_runtime_port

    if not _runtime_artifact_ready(runtime_root, runtime_metadata_path, runtime_artifact):
        runtime_plan_item = _require_download_plan_item(
            session,
            RUNTIME_ARTIFACT_DOWNLOAD_KEY,
        )
        if download_runtime_archive is None:
            download_runtime_archive = _download_file
        try:
            _stage_runtime_artifact(
                install_root=install_root,
                temp_root=temp_root,
                runtime_artifact=runtime_artifact,
                download_runtime_archive=download_runtime_archive,
                extract_archive=extract_archive,
                verify_archive_sha256=verify_archive_sha256,
                plan_item=runtime_plan_item,
            )
        except Exception as exc:
            session.runtime_payload_status = "failed"
            session.runtime_artifact_status = "failed"
            session.starter_model_status = "skipped"
            session.active_model_config_status = "skipped"
            session.model_locations_config_status = "skipped"
            session.runtime_endpoint_config_status = "skipped"
            session.failing_step = "runtime-artifact"
            session.error_message = str(exc)
            return session

    session.runtime_artifact_status = "ready"
    session.last_successful_step = "runtime-artifact"

    if not starter_model_path.exists() or not verify_model_file(
        starter_model_path, starter_model["sha256"]
    ):
        model_plan_item = _require_download_plan_item(
            session,
            starter_model_download_key(starter_model["id"]),
        )
        if download_model_file is None:
            download_model_file = _download_file
        try:
            _stage_starter_model(
                install_root=install_root,
                temp_root=temp_root,
                starter_model=starter_model,
                download_model_file=download_model_file,
                verify_model_file=verify_model_file,
                plan_item=model_plan_item,
            )
        except Exception as exc:
            session.runtime_payload_status = "failed"
            session.starter_model_status = "failed"
            session.active_model_config_status = "skipped"
            session.model_locations_config_status = "skipped"
            session.runtime_endpoint_config_status = "skipped"
            session.failing_step = "starter-model"
            session.error_message = str(exc)
            return session

    session.starter_model_status = "ready"
    session.last_successful_step = "starter-model"
    if write_active_model_config is None:
        write_active_model_config = _write_active_model_config
    if write_model_locations_config is None:
        write_model_locations_config = _write_model_locations_config
    if write_runtime_endpoint_config is None:
        write_runtime_endpoint_config = _write_runtime_endpoint_config
    try:
        write_active_model_config(
            active_model_config_path,
            model_id=starter_model["id"],
            model_path=starter_model_path,
        )
    except Exception as exc:
        session.runtime_payload_status = "failed"
        session.active_model_config_status = "failed"
        session.model_locations_config_status = "skipped"
        session.runtime_endpoint_config_status = "skipped"
        session.failing_step = "active-model-config"
        session.error_message = str(exc)
        return session
    session.active_model_config_status = "ready"
    session.last_successful_step = "active-model-config"

    try:
        write_model_locations_config(
            model_locations_config_path,
            default_model_root=model_root,
            additional_paths=normalized_additional_paths,
        )
    except Exception as exc:
        session.runtime_payload_status = "failed"
        session.model_locations_config_status = "failed"
        session.runtime_endpoint_config_status = "skipped"
        session.failing_step = "model-locations-config"
        session.error_message = str(exc)
        return session
    session.model_locations_config_status = "ready"
    session.last_successful_step = "model-locations-config"

    try:
        write_runtime_endpoint_config(
            runtime_endpoint_config_path,
            port=validated_managed_runtime_port,
        )
    except Exception as exc:
        session.runtime_payload_status = "failed"
        session.runtime_endpoint_config_status = "failed"
        session.failing_step = "runtime-endpoint-config"
        session.error_message = str(exc)
        return session
    session.runtime_endpoint_config_status = "ready"
    session.last_successful_step = "runtime-endpoint-config"
    session.runtime_payload_status = "ready"
    return session


def _runtime_artifact_ready(
    runtime_root: Path,
    metadata_path: Path,
    runtime_artifact: dict,
) -> bool:
    return verify_required_files(
        runtime_root, runtime_artifact["required_files"]
    ) and verify_required_file_checksums(
        runtime_root, runtime_artifact["required_file_sha256"]
    ) and verify_runtime_metadata(
        metadata_path,
        artifact_id=runtime_artifact["id"],
        source_sha256=runtime_artifact["sha256"],
    )


def _stage_runtime_artifact(
    *,
    install_root: Path,
    temp_root: Path,
    runtime_artifact: dict,
    download_runtime_archive,
    extract_archive,
    verify_archive_sha256,
    plan_item,
) -> None:
    staging_root = _make_staging_root(temp_root)
    archive_path = staging_root / "downloads" / "runtime-artifact.archive"
    extracted_root = staging_root / "payload" / runtime_artifact["install_subdir"]

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    _invoke_download(
        download_runtime_archive,
        runtime_artifact["url"],
        archive_path,
        plan_item=plan_item,
    )
    if not verify_archive_sha256(archive_path, runtime_artifact["sha256"]):
        raise ValueError("Runtime archive checksum verification failed.")

    extract_archive(
        archive_path,
        extracted_root,
        archive_type=runtime_artifact["archive_type"],
    )
    if not verify_required_files(extracted_root, runtime_artifact["required_files"]):
        raise ValueError("Runtime artifact is missing required files.")
    if not verify_required_file_checksums(
        extracted_root, runtime_artifact["required_file_sha256"]
    ):
        raise ValueError("Runtime artifact required file checksum verification failed.")

    write_runtime_metadata(
        extracted_root / "runtime-artifact.json",
        artifact_id=runtime_artifact["id"],
        source_sha256=runtime_artifact["sha256"],
    )
    promote_tree(staging_root / "payload", install_root)


def _stage_starter_model(
    *,
    install_root: Path,
    temp_root: Path,
    starter_model: dict,
    download_model_file,
    verify_model_file,
    plan_item,
) -> None:
    staging_root = _make_staging_root(temp_root)
    staged_model_path = (
        staging_root
        / "payload"
        / starter_model["install_subdir"]
        / starter_model["target_filename"]
    )

    staged_model_path.parent.mkdir(parents=True, exist_ok=True)
    _invoke_download(
        download_model_file,
        starter_model["url"],
        staged_model_path,
        plan_item=plan_item,
    )
    if not verify_model_file(staged_model_path, starter_model["sha256"]):
        raise ValueError("Starter model checksum verification failed.")

    promote_tree(staging_root / "payload", install_root)


def _write_active_model_config(
    active_model_config_path: Path,
    *,
    model_id: str,
    model_path: Path,
) -> Path:
    return _atomic_write_json(
        active_model_config_path,
        {
            "model_id": model_id,
            "model_path": str(model_path),
        },
    )


def _write_model_locations_config(
    model_locations_config_path: Path,
    *,
    default_model_root: Path,
    additional_paths: list[str],
) -> Path:
    return _atomic_write_json(
        model_locations_config_path,
        {
            "default_model_root": str(default_model_root),
            "additional_read_only_model_paths": list(additional_paths),
        },
    )


def _write_runtime_endpoint_config(
    runtime_endpoint_config_path: Path,
    *,
    port: int,
) -> Path:
    return _atomic_write_json(
        runtime_endpoint_config_path,
        {
            "base_url": f"http://127.0.0.1:{port}",
            "port": port,
            "installer_managed": True,
        },
    )


def _atomic_write_json(path: Path, payload: dict) -> Path:
    return _atomic_write_text(path, json.dumps(payload, indent=2))


def _atomic_write_text(path: Path, contents: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, staged_path_raw = mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    staged_path = Path(staged_path_raw)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            handle.write(contents)
        staged_path.replace(path)
    except Exception:
        try:
            staged_path.unlink()
        except OSError:
            pass
        raise
    return path


def _validate_managed_runtime_port(port: object) -> int:
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError(
            "Managed runtime port must be an integer between 1 and 65535."
        )
    return port


def _normalize_additional_model_paths(additional_paths: list[str]) -> list[str]:
    normalized_paths: list[str] = []
    seen_paths: set[str] = set()

    for raw_path in additional_paths:
        normalized = str(raw_path).strip()
        if not normalized:
            continue
        normalized_path = str(Path(normalized))
        dedupe_key = os.path.normcase(os.path.normpath(normalized_path))
        if dedupe_key in seen_paths:
            continue
        seen_paths.add(dedupe_key)
        normalized_paths.append(normalized_path)

    return normalized_paths


def _make_staging_root(temp_root: Path) -> Path:
    temp_root.mkdir(parents=True, exist_ok=True)
    return Path(mkdtemp(prefix="runtime-payload-", dir=str(temp_root)))


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
