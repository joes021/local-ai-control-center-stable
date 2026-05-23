from __future__ import annotations

from collections.abc import Callable, Mapping
import ctypes
from importlib.resources import files
import inspect
import json
from json import JSONDecodeError
from pathlib import Path
import platform as platform_module
import shutil
import subprocess
from tempfile import mkdtemp, gettempdir

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
    TURBOQUANT_ARTIFACT_DOWNLOAD_KEY,
    find_download_plan_item,
)
from .runtime_binary_health import detect_missing_sidecar_imports
from .session import InstallerSession


NO_WINDOWS_STRATEGY_ERROR = (
    "No packaged Windows TurboQuant strategy is available in this installer build."
)
UNSUPPORTED_WINDOWS_TURBOQUANT_ERROR = (
    "Packaged TurboQuant currently supports only Windows x64 with an NVIDIA driver "
    "that exposes nvidia-smi."
)
NVIDIA_SMI_QUERY_TIMEOUT_SECONDS = 20
DEFAULT_NVSMI_PATH = Path(
    r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"
)

StrategyResolver = Callable[[], object | None]
StrategyInstaller = Callable[[InstallerSession, object], InstallerSession | None]


def load_turboquant_manifest(manifest_path=None) -> dict:
    if manifest_path is None:
        manifest_path = files("local_ai_control_center_installer.manifests").joinpath(
            "windows-stable-turboquant.json"
        )

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("TurboQuant manifest top-level object must be a JSON object.")
    if "turboquant_artifact" not in payload:
        raise ValueError("TurboQuant manifest is missing required top-level fields.")

    _validate_turboquant_artifact(payload["turboquant_artifact"])
    return payload


def resolve_packaged_windows_strategy(
    *,
    load_manifest=load_turboquant_manifest,
    platform_system: Callable[[], str] | None = None,
    platform_machine: Callable[[], str] | None = None,
    query_nvidia_smi=None,
) -> dict:
    platform_system = platform_system or platform_module.system
    platform_machine = platform_machine or platform_module.machine
    query_nvidia_smi = query_nvidia_smi or _query_nvidia_smi

    if platform_system().strip().lower() != "windows":
        raise ValueError(UNSUPPORTED_WINDOWS_TURBOQUANT_ERROR)

    normalized_machine = platform_machine().strip().lower()
    if normalized_machine not in {"amd64", "x86_64"}:
        raise ValueError(UNSUPPORTED_WINDOWS_TURBOQUANT_ERROR)

    nvidia_rows = query_nvidia_smi()
    if not nvidia_rows:
        raise ValueError(UNSUPPORTED_WINDOWS_TURBOQUANT_ERROR)

    manifest = load_manifest()
    turboquant_artifact = manifest["turboquant_artifact"]
    return {
        "artifact": turboquant_artifact,
        "executable_relative_path": turboquant_artifact["launch"][
            "executable_relative_path"
        ],
        "nvidia_smi_rows": tuple(nvidia_rows),
    }


def apply_turboquant(
    session: InstallerSession,
    *,
    temp_root: Path | None = None,
    load_manifest=load_turboquant_manifest,
    resolve_windows_strategy: StrategyResolver | None = None,
    install_strategy: StrategyInstaller | None = None,
    download_archive=None,
    extract_archive=extract_archive,
    verify_archive_sha256=verify_sha256,
    verify_required_file_checksums=verify_required_file_checksums,
    query_nvidia_smi=None,
    load_library=None,
) -> InstallerSession:
    if session.attempt_turboquant is not True:
        session.turboquant_status = "skipped"
        session.turboquant_error = None
        return session

    if not _core_prerequisites_ready(session):
        session.turboquant_status = "skipped"
        session.turboquant_error = None
        return session

    normalized_install_root = (session.install_root or "").strip()
    if not normalized_install_root:
        session.turboquant_status = "failed"
        session.turboquant_error = "TurboQuant install root is required."
        return session

    install_root = Path(normalized_install_root).expanduser().resolve()
    session.install_root = str(install_root)
    temp_root = temp_root or Path(gettempdir())
    resolve_windows_strategy = resolve_windows_strategy or (
        lambda: resolve_packaged_windows_strategy(
            load_manifest=load_manifest,
            query_nvidia_smi=query_nvidia_smi,
        )
    )

    try:
        raw_strategy = resolve_windows_strategy()
    except Exception as exc:
        session.turboquant_status = "failed"
        session.turboquant_error = str(exc)
        return session

    if raw_strategy is None:
        session.turboquant_status = "failed"
        session.turboquant_error = NO_WINDOWS_STRATEGY_ERROR
        return session

    strategy = _coerce_packaged_windows_strategy(raw_strategy)
    turboquant_artifact = strategy["artifact"]
    turboquant_root = install_root / turboquant_artifact["install_subdir"]
    turboquant_metadata_path = turboquant_root / "turboquant-artifact.json"
    turboquant_executable_path = (
        turboquant_root / strategy["executable_relative_path"]
    )

    session.turboquant_artifact_id = turboquant_artifact["id"]
    session.turboquant_artifact_path = str(turboquant_root)
    session.turboquant_metadata_path = str(turboquant_metadata_path)
    session.turboquant_executable_path = str(turboquant_executable_path)

    if _turboquant_artifact_ready(
        turboquant_root,
        turboquant_metadata_path,
        turboquant_artifact,
        verify_required_file_checksums=verify_required_file_checksums,
        load_library=load_library,
    ):
        session.turboquant_status = "ready"
        session.turboquant_error = None
        session.last_successful_step = "turboquant-artifact"
        return session

    if install_strategy is None:
        install_strategy = lambda current_session, current_strategy: _install_packaged_windows_strategy(
            current_session,
            current_strategy,
            install_root=install_root,
            temp_root=temp_root,
            download_archive=download_archive,
            extract_archive=extract_archive,
            verify_archive_sha256=verify_archive_sha256,
            verify_required_file_checksums=verify_required_file_checksums,
            load_library=load_library,
        )

    try:
        updated = install_strategy(session, strategy) or session
    except Exception as exc:
        session.turboquant_status = "failed"
        session.turboquant_error = str(exc)
        return session

    if updated.turboquant_status == "skipped":
        updated.turboquant_status = "ready"
    if updated.turboquant_status == "ready":
        updated.turboquant_error = None
    return updated


def _core_prerequisites_ready(session: InstallerSession) -> bool:
    return (
        session.bootstrap_status == "ready"
        and session.runtime_payload_status == "ready"
        and session.server_verification_status == "ready"
        and session.opencode_artifact_status == "ready"
        and session.opencode_verification_status == "ready"
    )


def _validate_turboquant_artifact(turboquant_artifact: dict) -> None:
    if not isinstance(turboquant_artifact, dict):
        raise ValueError("TurboQuant artifact entry must be an object.")

    for key in ("id", "url", "sha256", "archive_type", "install_subdir"):
        _validate_manifest_string_field(
            turboquant_artifact,
            key,
            context="TurboQuant artifact entry",
        )

    required_files = turboquant_artifact.get("required_files")
    if not isinstance(required_files, list) or not required_files:
        raise ValueError(
            "TurboQuant artifact entry required_files must be a non-empty list."
        )
    for relative_path in required_files:
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise ValueError(
                "TurboQuant artifact entry required_files must contain non-empty string paths."
            )

    required_file_sha256 = turboquant_artifact.get("required_file_sha256")
    if not isinstance(required_file_sha256, dict):
        raise ValueError(
            "TurboQuant artifact entry required_file_sha256 must be an object."
        )
    for relative_path, checksum in required_file_sha256.items():
        if relative_path not in required_files:
            raise ValueError(
                "TurboQuant artifact entry required_file_sha256 contains an unknown required file."
            )
        if not isinstance(checksum, str) or not checksum.strip():
            raise ValueError(
                f"TurboQuant artifact entry required_file_sha256 has invalid value for: {relative_path}"
            )

    size_bytes = turboquant_artifact.get("size_bytes")
    if not isinstance(size_bytes, int) or size_bytes < 1:
        raise ValueError(
            "TurboQuant artifact entry size_bytes must be a positive integer."
        )

    launch = turboquant_artifact.get("launch")
    if not isinstance(launch, dict):
        raise ValueError("TurboQuant artifact entry launch must be an object.")

    executable_relative_path = _validate_manifest_string_field(
        launch,
        "executable_relative_path",
        context="TurboQuant artifact launch entry",
    )
    if executable_relative_path not in required_files:
        raise ValueError(
            "TurboQuant artifact launch entry executable_relative_path must be listed in required_files."
        )


def _validate_manifest_string_field(
    payload: dict,
    key: str,
    *,
    context: str,
) -> str:
    if key not in payload:
        raise ValueError(f"{context} is missing required field: {key}")

    value = payload[key]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} field must be a non-empty string: {key}")
    return value


def _coerce_packaged_windows_strategy(raw_strategy: object) -> dict:
    if not isinstance(raw_strategy, Mapping):
        raise ValueError("TurboQuant packaged strategy must be an object.")

    artifact = raw_strategy.get("artifact")
    if not isinstance(artifact, dict):
        raise ValueError("TurboQuant packaged strategy must include an artifact object.")

    _validate_turboquant_artifact(artifact)
    executable_relative_path = raw_strategy.get("executable_relative_path")
    if not isinstance(executable_relative_path, str) or not executable_relative_path.strip():
        raise ValueError(
            "TurboQuant packaged strategy must include a non-empty executable_relative_path."
        )
    if executable_relative_path not in artifact["required_files"]:
        raise ValueError(
            "TurboQuant packaged strategy executable_relative_path must be listed in required_files."
        )

    return {
        "artifact": artifact,
        "executable_relative_path": executable_relative_path,
    }


def _turboquant_artifact_ready(
    turboquant_root: Path,
    metadata_path: Path,
    turboquant_artifact: dict,
    *,
    verify_required_file_checksums,
    load_library=None,
) -> bool:
    executable_path = _resolve_turboquant_executable_path(
        turboquant_root,
        turboquant_artifact,
    )
    return (
        verify_required_files(turboquant_root, turboquant_artifact["required_files"])
        and verify_required_file_checksums(
            turboquant_root, turboquant_artifact["required_file_sha256"]
        )
        and verify_runtime_metadata(
            metadata_path,
            artifact_id=turboquant_artifact["id"],
            source_sha256=turboquant_artifact["sha256"],
        )
        and _verify_bundled_libraries_load(
            turboquant_root,
            turboquant_artifact["required_files"],
            load_library=load_library,
        )
        and not detect_missing_sidecar_imports(executable_path)
    )


def _install_packaged_windows_strategy(
    session: InstallerSession,
    strategy: object,
    *,
    install_root: Path,
    temp_root: Path,
    download_archive=None,
    extract_archive=extract_archive,
    verify_archive_sha256=verify_sha256,
    verify_required_file_checksums=verify_required_file_checksums,
    load_library=None,
) -> InstallerSession:
    strategy = _coerce_packaged_windows_strategy(strategy)
    turboquant_artifact = strategy["artifact"]
    plan_item = _require_download_plan_item(session, TURBOQUANT_ARTIFACT_DOWNLOAD_KEY)
    if download_archive is None:
        download_archive = _download_file

    staging_root = _make_staging_root(temp_root)
    archive_path = staging_root / "downloads" / "turboquant-artifact.archive"
    extracted_root = staging_root / "payload" / turboquant_artifact["install_subdir"]

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    _invoke_download(
        download_archive,
        turboquant_artifact["url"],
        archive_path,
        plan_item=plan_item,
    )
    if not verify_archive_sha256(archive_path, turboquant_artifact["sha256"]):
        raise ValueError("TurboQuant archive checksum verification failed.")

    extract_archive(
        archive_path,
        extracted_root,
        archive_type=turboquant_artifact["archive_type"],
    )
    if not verify_required_files(extracted_root, turboquant_artifact["required_files"]):
        raise ValueError("TurboQuant artifact is missing required files.")
    if not verify_required_file_checksums(
        extracted_root, turboquant_artifact["required_file_sha256"]
    ):
        raise ValueError("TurboQuant artifact required file checksum verification failed.")

    if not _verify_bundled_libraries_load(
        extracted_root,
        turboquant_artifact["required_files"],
        load_library=load_library,
    ):
        raise ValueError(
            "TurboQuant bundled libraries could not be loaded on this machine."
        )

    missing_sidecars = detect_missing_sidecar_imports(
        _resolve_turboquant_executable_path(extracted_root, turboquant_artifact)
    )
    if missing_sidecars:
        missing_labels = ", ".join(missing_sidecars)
        raise ValueError(
            f"TurboQuant executable is missing required sidecar DLLs: {missing_labels}."
        )

    write_runtime_metadata(
        extracted_root / "turboquant-artifact.json",
        artifact_id=turboquant_artifact["id"],
        source_sha256=turboquant_artifact["sha256"],
    )
    promote_tree(staging_root / "payload", install_root)

    session.turboquant_status = "ready"
    session.turboquant_error = None
    session.last_successful_step = "turboquant-artifact"
    return session


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


def _make_staging_root(temp_root: Path) -> Path:
    temp_root.mkdir(parents=True, exist_ok=True)
    return Path(mkdtemp(prefix="turboquant-payload-", dir=str(temp_root)))


def _require_download_plan_item(session: InstallerSession, key: str):
    plan_item = find_download_plan_item(session.download_plan, key)
    if plan_item is None:
        raise ValueError(f"Installer session download plan is missing item: {key}")
    return plan_item


def _resolve_turboquant_executable_path(
    root: Path,
    turboquant_artifact: dict,
) -> Path:
    launch = turboquant_artifact.get("launch", {})
    executable_relative_path = str(
        launch.get("executable_relative_path", "llama-server.exe")
    )
    return root / executable_relative_path


def _invoke_download(download_func, url: str, destination: Path, *, plan_item) -> Path:
    parameters = inspect.signature(download_func).parameters.values()
    if any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters):
        return download_func(url, destination, plan_item=plan_item)
    if "plan_item" in inspect.signature(download_func).parameters:
        return download_func(url, destination, plan_item=plan_item)
    return download_func(url, destination)


def _resolve_nvidia_smi_path() -> Path | None:
    discovered_path = shutil.which("nvidia-smi")
    if discovered_path:
        return Path(discovered_path)
    if DEFAULT_NVSMI_PATH.exists():
        return DEFAULT_NVSMI_PATH
    return None


def _query_nvidia_smi() -> tuple[str, ...]:
    nvidia_smi_path = _resolve_nvidia_smi_path()
    if nvidia_smi_path is None:
        return ()

    try:
        result = subprocess.run(
            [
                str(nvidia_smi_path),
                "--query-gpu=name,driver_version",
                "--format=csv,noheader",
            ],
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=NVIDIA_SMI_QUERY_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ()

    if result.returncode != 0:
        return ()

    rows = tuple(line.strip() for line in result.stdout.splitlines() if line.strip())
    return rows


def _verify_bundled_libraries_load(
    root: Path,
    required_files: list[str],
    *,
    load_library=None,
) -> bool:
    load_library = load_library or ctypes.WinDLL
    try:
        for relative_path in required_files:
            if not relative_path.lower().endswith(".dll"):
                continue
            load_library(str(root / relative_path))
    except OSError:
        return False
    return True
