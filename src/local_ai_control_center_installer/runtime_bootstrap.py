import json
from importlib.resources import files
from pathlib import Path
from tempfile import mkdtemp
from urllib.request import urlopen

from .downloads import (
    extract_archive,
    promote_tree,
    verify_required_files,
    verify_runtime_metadata,
    verify_sha256,
    write_runtime_metadata,
)
from .session import InstallerSession


def load_runtime_manifest(manifest_path=None) -> dict:
    if manifest_path is None:
        manifest_path = files("local_ai_control_center_installer.manifests").joinpath(
            "windows-stable-runtime.json"
        )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if "runtime_artifact" not in payload or "starter_models" not in payload:
        raise ValueError("Runtime manifest is missing required top-level fields.")
    runtime_artifact = payload["runtime_artifact"]
    for key in (
        "id",
        "url",
        "sha256",
        "archive_type",
        "required_files",
        "install_subdir",
    ):
        if key not in runtime_artifact:
            raise ValueError(f"Runtime artifact entry is missing required field: {key}")
    return payload


def resolve_requested_starter_model(manifest: dict, requested_model_id: str) -> dict:
    starter_models = manifest.get("starter_models")
    if not isinstance(starter_models, dict):
        raise ValueError("Runtime manifest starter_models entry must be an object.")

    try:
        starter_model = starter_models[requested_model_id]
    except KeyError as exc:
        raise ValueError(f"Missing starter model entry for {requested_model_id}") from exc

    if not isinstance(starter_model, dict):
        raise ValueError(
            f"Starter model entry for {requested_model_id} must be an object."
        )

    for key in ("id", "url", "sha256", "target_filename", "install_subdir"):
        if key not in starter_model:
            raise ValueError(
                f"Starter model entry for {requested_model_id} is missing required field: {key}"
            )
    return starter_model


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
) -> InstallerSession:
    if session.bootstrap_status != "ready":
        session.runtime_payload_status = "skipped"
        session.runtime_artifact_status = "skipped"
        session.starter_model_status = "skipped"
        session.active_model_config_status = "skipped"
        return session

    session.failing_step = None
    session.last_successful_step = None

    install_root = Path(session.install_root).expanduser().resolve()
    session.install_root = str(install_root)
    try:
        manifest = load_manifest()
    except ValueError:
        session.runtime_payload_status = "failed"
        session.runtime_artifact_status = "failed"
        session.starter_model_status = "failed"
        session.active_model_config_status = "skipped"
        session.failing_step = "runtime-manifest"
        return session
    runtime_artifact = manifest["runtime_artifact"]
    try:
        starter_model = resolve_requested_starter_model(manifest, session.starter_model)
    except ValueError:
        session.runtime_payload_status = "failed"
        session.runtime_artifact_status = "skipped"
        session.starter_model_status = "failed"
        session.active_model_config_status = "skipped"
        session.failing_step = "runtime-manifest"
        return session

    runtime_root = install_root / runtime_artifact["install_subdir"]
    runtime_metadata_path = runtime_root / "runtime-artifact.json"
    model_root = install_root / starter_model["install_subdir"]
    starter_model_path = model_root / starter_model["target_filename"]
    active_model_config_path = install_root / "config" / "active-model.json"

    session.runtime_artifact_id = runtime_artifact["id"]
    session.runtime_artifact_path = str(runtime_root)
    session.runtime_metadata_path = str(runtime_metadata_path)
    session.starter_model_path = str(starter_model_path)
    session.active_model_config_path = str(active_model_config_path)

    if not _runtime_artifact_ready(runtime_root, runtime_metadata_path, runtime_artifact):
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
            )
        except Exception:
            session.runtime_payload_status = "failed"
            session.runtime_artifact_status = "failed"
            session.starter_model_status = "skipped"
            session.active_model_config_status = "skipped"
            session.failing_step = "runtime-artifact"
            return session

    session.runtime_artifact_status = "ready"
    session.last_successful_step = "runtime-artifact"

    if not starter_model_path.exists() or not verify_model_file(
        starter_model_path, starter_model["sha256"]
    ):
        if download_model_file is None:
            download_model_file = _download_file
        try:
            _stage_starter_model(
                install_root=install_root,
                temp_root=temp_root,
                starter_model=starter_model,
                download_model_file=download_model_file,
                verify_model_file=verify_model_file,
            )
        except Exception:
            session.runtime_payload_status = "failed"
            session.starter_model_status = "failed"
            session.active_model_config_status = "skipped"
            session.failing_step = "starter-model"
            return session

    session.starter_model_status = "ready"
    session.last_successful_step = "starter-model"
    if write_active_model_config is None:
        write_active_model_config = _write_active_model_config
    try:
        write_active_model_config(
            active_model_config_path,
            model_id=starter_model["id"],
            model_path=starter_model_path,
        )
    except Exception:
        session.runtime_payload_status = "failed"
        session.active_model_config_status = "failed"
        session.failing_step = "active-model-config"
        return session
    session.active_model_config_status = "ready"
    session.last_successful_step = "active-model-config"
    session.runtime_payload_status = "ready"
    return session


def _runtime_artifact_ready(
    runtime_root: Path,
    metadata_path: Path,
    runtime_artifact: dict,
) -> bool:
    return verify_required_files(
        runtime_root, runtime_artifact["required_files"]
    ) and verify_runtime_metadata(
        metadata_path,
        artifact_id=runtime_artifact["id"],
        source_sha256=runtime_artifact["sha256"],
        root=runtime_root,
        required_files=runtime_artifact["required_files"],
    )


def _stage_runtime_artifact(
    *,
    install_root: Path,
    temp_root: Path,
    runtime_artifact: dict,
    download_runtime_archive,
    extract_archive,
    verify_archive_sha256,
) -> None:
    staging_root = _make_staging_root(temp_root)
    archive_path = staging_root / "downloads" / "runtime-artifact.archive"
    extracted_root = staging_root / "payload" / runtime_artifact["install_subdir"]

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    download_runtime_archive(runtime_artifact["url"], archive_path)
    if not verify_archive_sha256(archive_path, runtime_artifact["sha256"]):
        raise ValueError("Runtime archive checksum verification failed.")

    extract_archive(
        archive_path,
        extracted_root,
        archive_type=runtime_artifact["archive_type"],
    )
    if not verify_required_files(extracted_root, runtime_artifact["required_files"]):
        raise ValueError("Runtime artifact is missing required files.")

    write_runtime_metadata(
        extracted_root / "runtime-artifact.json",
        artifact_id=runtime_artifact["id"],
        source_sha256=runtime_artifact["sha256"],
        root=extracted_root,
        required_files=runtime_artifact["required_files"],
    )
    promote_tree(staging_root / "payload", install_root)


def _stage_starter_model(
    *,
    install_root: Path,
    temp_root: Path,
    starter_model: dict,
    download_model_file,
    verify_model_file,
) -> None:
    staging_root = _make_staging_root(temp_root)
    staged_model_path = (
        staging_root
        / "payload"
        / starter_model["install_subdir"]
        / starter_model["target_filename"]
    )

    staged_model_path.parent.mkdir(parents=True, exist_ok=True)
    download_model_file(starter_model["url"], staged_model_path)
    if not verify_model_file(staged_model_path, starter_model["sha256"]):
        raise ValueError("Starter model checksum verification failed.")

    promote_tree(staging_root / "payload", install_root)


def _write_active_model_config(
    active_model_config_path: Path,
    *,
    model_id: str,
    model_path: Path,
) -> Path:
    active_model_config_path.parent.mkdir(parents=True, exist_ok=True)
    active_model_config_path.write_text(
        json.dumps(
            {
                "model_id": model_id,
                "model_path": str(model_path),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return active_model_config_path


def _make_staging_root(temp_root: Path) -> Path:
    temp_root.mkdir(parents=True, exist_ok=True)
    return Path(mkdtemp(prefix="runtime-payload-", dir=str(temp_root)))


def _download_file(url: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url) as response:
        destination.write_bytes(response.read())
    return destination
