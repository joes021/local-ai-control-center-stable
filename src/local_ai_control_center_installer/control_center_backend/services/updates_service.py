from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from local_ai_control_center_installer.control_center_backend.config import (
    ControlCenterConfig,
    get_config,
)
from local_ai_control_center_installer.control_center_backend.services.state_helpers import (
    action_result,
    atomic_write_json,
    read_json_object,
)
from local_ai_control_center_installer.control_center_backend.services.status_service import (
    _detect_version,
)
from local_ai_control_center_installer.downloads import (
    DownloadProgress,
    download_file as shared_download_file,
)
from local_ai_control_center_installer.platform_paths import (
    build_worker_launch_spec,
    new_console_subprocess_creationflags,
)


GITHUB_RELEASES_LATEST_URL = (
    "https://api.github.com/repos/joes021/local-ai-control-center-stable/releases/latest"
)
GITHUB_RELEASE_TIMEOUT_SECONDS = 20.0
UPDATE_PROGRESS_STALE_SECONDS = 15.0
ACTIVE_UPDATE_STATUSES = {
    "checking",
    "starting",
    "downloading",
    "launching-installer",
}
IDLE_UPDATE_PROGRESS: dict[str, object] = {
    "actionId": "",
    "status": "idle",
    "phase": "idle",
    "isActive": False,
    "currentVersion": "",
    "latestVersion": "",
    "releaseUrl": "",
    "targetPath": "",
    "percent": None,
    "downloadedGiB": None,
    "totalGiB": None,
    "speedMBps": None,
    "etaSeconds": None,
    "message": "Nema aktivnog update toka.",
    "updatedAt": "",
    "workerPid": None,
}


def check_for_updates(
    config: ControlCenterConfig | None = None,
    *,
    latest_release_fetcher=None,
) -> dict[str, object]:
    config = config or get_config()
    latest_release_fetcher = latest_release_fetcher or fetch_latest_release_metadata

    try:
        candidate = _resolve_update_candidate(config, latest_release_fetcher)
    except Exception as exc:  # noqa: BLE001
        progress = _build_error_progress(
            config,
            current_version=detect_installed_version(config),
            message=f"Provera update-a nije uspela: {exc}",
        )
        _write_update_progress(config, progress)
        return action_result(
            "error",
            "check-updates",
            progress["message"],
            stderr=str(exc),
        )

    if not candidate["updateAvailable"]:
        progress = _build_up_to_date_progress(candidate)
        _write_update_progress(config, progress)
        return action_result(
            "ok",
            "check-updates",
            f"Već koristiš najnoviju verziju ({candidate['currentVersion']}).",
        )

    progress = _build_available_update_progress(candidate)
    _write_update_progress(config, progress)
    return action_result(
        "ok",
        "check-updates",
        f"Dostupna je nova verzija {candidate['latestVersion']} (trenutno {candidate['currentVersion']}).",
        stdout=json.dumps(
            {
                "currentVersion": candidate["currentVersion"],
                "latestVersion": candidate["latestVersion"],
                "releaseUrl": candidate["releaseUrl"],
                "targetPath": candidate["targetPath"],
            },
            ensure_ascii=False,
        ),
    )


def install_update(
    config: ControlCenterConfig | None = None,
    *,
    latest_release_fetcher=None,
) -> dict[str, object]:
    config = config or get_config()
    latest_release_fetcher = latest_release_fetcher or fetch_latest_release_metadata
    current_progress = load_update_progress_payload(config)
    if bool(current_progress.get("isActive")):
        return action_result(
            "error",
            "install-update",
            "Update je već u toku. Sačekaj da se završi pre novog pokušaja.",
            stderr="Update je već aktivan.",
        )

    try:
        candidate = _resolve_update_candidate(config, latest_release_fetcher)
    except Exception as exc:  # noqa: BLE001
        progress = _build_error_progress(
            config,
            current_version=detect_installed_version(config),
            message=f"Priprema update-a nije uspela: {exc}",
        )
        _write_update_progress(config, progress)
        return action_result(
            "error",
            "install-update",
            progress["message"],
            stderr=str(exc),
        )

    if not candidate["updateAvailable"]:
        progress = _build_up_to_date_progress(candidate)
        _write_update_progress(config, progress)
        return action_result(
            "ok",
            "install-update",
            f"Već koristiš najnoviju verziju ({candidate['currentVersion']}).",
        )

    action_id = f"update-{uuid4().hex[:8]}"
    try:
        process = _spawn_update_worker(action_id, config)
    except OSError as exc:
        progress = _build_error_progress(
            config,
            current_version=str(candidate["currentVersion"]),
            latest_version=str(candidate["latestVersion"]),
            release_url=str(candidate["releaseUrl"]),
            target_path=str(candidate["targetPath"]),
            message=f"Pokretanje update worker-a nije uspelo: {exc}",
        )
        _write_update_progress(config, progress)
        return action_result(
            "error",
            "install-update",
            progress["message"],
            stderr=str(exc),
        )

    progress = {
        "actionId": action_id,
        "status": "starting",
        "phase": "queued",
        "isActive": True,
        "currentVersion": str(candidate["currentVersion"]),
        "latestVersion": str(candidate["latestVersion"]),
        "releaseUrl": str(candidate["releaseUrl"]),
        "targetPath": str(candidate["targetPath"]),
        "percent": 0.0,
        "downloadedGiB": 0.0,
        "totalGiB": _to_gib(_coerce_int(candidate["installerSizeBytes"])),
        "speedMBps": None,
        "etaSeconds": None,
        "message": f"Pokrenut je update ka verziji {candidate['latestVersion']}.",
        "updatedAt": _utc_now(),
        "workerPid": getattr(process, "pid", None),
    }
    _write_update_progress(config, progress)
    return action_result(
        "accepted",
        "install-update",
        f"Update ka verziji {candidate['latestVersion']} je pokrenut.",
        action_id=action_id,
        stdout=json.dumps(
            {
                "pid": getattr(process, "pid", None),
                "targetPath": candidate["targetPath"],
            },
            ensure_ascii=False,
        ),
    )


def load_update_progress_payload(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    payload = read_json_object(config.update_progress_path)
    if not payload:
        return dict(IDLE_UPDATE_PROGRESS)

    normalized = _normalize_update_progress_payload(payload)
    if _is_dead_active_update(normalized):
        normalized = {
            **normalized,
            "status": "error",
            "phase": "error",
            "isActive": False,
            "message": "Update worker više nije aktivan. Pokreni update ponovo.",
            "updatedAt": _utc_now(),
            "workerPid": None,
        }
        _write_update_progress(config, normalized)
    return normalized


def run_update_install_worker(
    action_id: str,
    *,
    config: ControlCenterConfig | None = None,
    latest_release_fetcher=None,
    download_file=shared_download_file,
    launch_installer=None,
) -> dict[str, object]:
    config = config or get_config()
    latest_release_fetcher = latest_release_fetcher or fetch_latest_release_metadata
    launch_installer = launch_installer or _launch_installer

    try:
        candidate = _resolve_update_candidate(config, latest_release_fetcher)
        if not candidate["updateAvailable"]:
            progress = _build_up_to_date_progress(candidate, action_id=action_id)
            _write_update_progress(config, progress)
            return action_result(
                "ok",
                "install-update-worker",
                f"Već koristiš najnoviju verziju ({candidate['currentVersion']}).",
                action_id=action_id,
            )

        target_path = Path(str(candidate["targetPath"]))
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_target_path = target_path.with_suffix(target_path.suffix + ".download")
        temp_target_path.unlink(missing_ok=True)
        start_time = time.monotonic()

        def progress_callback(progress: DownloadProgress) -> None:
            elapsed = max(time.monotonic() - start_time, 0.0)
            speed_mb = None
            if elapsed > 0 and progress.bytes_downloaded > 0:
                speed_mb = round(progress.bytes_downloaded / elapsed / (1024 * 1024), 1)
            _write_update_progress(
                config,
                {
                    "actionId": action_id,
                    "status": "downloading",
                    "phase": "download",
                    "isActive": True,
                    "currentVersion": str(candidate["currentVersion"]),
                    "latestVersion": str(candidate["latestVersion"]),
                    "releaseUrl": str(candidate["releaseUrl"]),
                    "targetPath": str(target_path),
                    "percent": _calculate_percent(
                        progress.bytes_downloaded,
                        progress.total_bytes,
                    ),
                    "downloadedGiB": _to_gib(progress.bytes_downloaded),
                    "totalGiB": _to_gib(progress.total_bytes),
                    "speedMBps": speed_mb,
                    "etaSeconds": _coerce_eta(progress.eta_seconds),
                    "message": f"Download je u toku za installer {candidate['latestVersion']}.",
                    "updatedAt": _utc_now(),
                    "workerPid": os.getpid(),
                },
            )

        download_file(
            str(candidate["installerDownloadUrl"]),
            temp_target_path,
            progress_callback=progress_callback,
            plan_item={
                "size_bytes": _coerce_int(candidate["installerSizeBytes"]),
            },
        )
        temp_target_path.replace(target_path)

        _write_update_progress(
            config,
            {
                "actionId": action_id,
                "status": "launching-installer",
                "phase": "launch-installer",
                "isActive": True,
                "currentVersion": str(candidate["currentVersion"]),
                "latestVersion": str(candidate["latestVersion"]),
                "releaseUrl": str(candidate["releaseUrl"]),
                "targetPath": str(target_path),
                "percent": 100.0,
                "downloadedGiB": _to_gib(target_path.stat().st_size),
                "totalGiB": _to_gib(target_path.stat().st_size),
                "speedMBps": None,
                "etaSeconds": 0,
                "message": "Installer je preuzet. Pokrećem update prozor.",
                "updatedAt": _utc_now(),
                "workerPid": os.getpid(),
            },
        )

        launch_installer(target_path, config)
        _write_update_progress(
            config,
            {
                "actionId": action_id,
                "status": "completed",
                "phase": "installer-launched",
                "isActive": False,
                "currentVersion": str(candidate["currentVersion"]),
                "latestVersion": str(candidate["latestVersion"]),
                "releaseUrl": str(candidate["releaseUrl"]),
                "targetPath": str(target_path),
                "percent": 100.0,
                "downloadedGiB": _to_gib(target_path.stat().st_size),
                "totalGiB": _to_gib(target_path.stat().st_size),
                "speedMBps": None,
                "etaSeconds": 0,
                "message": "Installer je pokrenut. Prati installer prozor da bi update bio završen.",
                "updatedAt": _utc_now(),
                "workerPid": None,
            },
        )
        return action_result(
            "ok",
            "install-update-worker",
            f"Installer za verziju {candidate['latestVersion']} je pokrenut.",
            action_id=action_id,
            stdout=str(target_path),
        )
    except Exception as exc:  # noqa: BLE001
        _write_update_progress(
            config,
            {
                "actionId": action_id,
                "status": "error",
                "phase": "error",
                "isActive": False,
                "currentVersion": detect_installed_version(config),
                "latestVersion": "",
                "releaseUrl": "",
                "targetPath": "",
                "percent": None,
                "downloadedGiB": None,
                "totalGiB": None,
                "speedMBps": None,
                "etaSeconds": None,
                "message": str(exc),
                "updatedAt": _utc_now(),
                "workerPid": None,
            },
        )
        return action_result(
            "error",
            "install-update-worker",
            str(exc),
            action_id=action_id,
            stderr=str(exc),
        )


def detect_installed_version(config: ControlCenterConfig | None = None) -> str:
    detected = str(_detect_version(config)).strip()
    return detected or "unknown"


def fetch_latest_release_metadata() -> dict[str, object]:
    request = Request(
        GITHUB_RELEASES_LATEST_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "LocalAIControlCenterUpdater/1.0",
        },
    )
    try:
        with urlopen(request, timeout=GITHUB_RELEASE_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"GitHub release API returned HTTP {exc.code}") from exc
    except URLError as exc:
        if _can_fallback_to_windows_release_request(exc):
            payload = _fetch_latest_release_metadata_via_windows_rest()
        else:
            raise RuntimeError(f"GitHub release API is unavailable: {exc.reason}") from exc
    except ssl.SSLCertVerificationError as exc:
        if _can_fallback_to_windows_release_request(exc):
            payload = _fetch_latest_release_metadata_via_windows_rest()
        else:
            raise RuntimeError(f"GitHub release API is unavailable: {exc}") from exc
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"GitHub release API returned invalid data: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("GitHub release payload is not an object.")
    return _normalize_release_payload(payload)


def _can_fallback_to_windows_release_request(exc: Exception) -> bool:
    if os.name != "nt":
        return False

    reason = getattr(exc, "reason", None)
    if isinstance(exc, ssl.SSLCertVerificationError) or isinstance(
        reason, ssl.SSLCertVerificationError
    ):
        return True

    message_parts = [str(exc)]
    if reason is not None:
        message_parts.append(str(reason))
    message = " ".join(part for part in message_parts if part).lower()
    return (
        "certificate_verify_failed" in message
        or "unable to get local issuer certificate" in message
        or "basic constraints of ca cert not marked critical" in message
    )


def _fetch_latest_release_metadata_via_windows_rest() -> dict[str, object]:
    command = [
        "powershell.exe",
        "-NoProfile",
        "-Command",
        (
            "$ProgressPreference='SilentlyContinue'; "
            "$headers=@{ 'Accept'='application/vnd.github+json'; 'User-Agent'='LocalAIControlCenterUpdater/1.0' }; "
            f"$resp = Invoke-RestMethod -Uri '{GITHUB_RELEASES_LATEST_URL}' -Headers $headers -TimeoutSec {int(GITHUB_RELEASE_TIMEOUT_SECONDS)}; "
            "$resp | ConvertTo-Json -Depth 20 -Compress"
        ),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        error_text = (
            completed.stderr.strip()
            or completed.stdout.strip()
            or "Windows release metadata fallback nije uspeo."
        )
        raise RuntimeError(f"GitHub release API is unavailable: {error_text}")

    try:
        payload = json.loads(completed.stdout)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"GitHub release API returned invalid data via Windows fallback: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise RuntimeError("GitHub release API returned non-object payload via Windows fallback.")
    return payload


def _normalize_release_payload(payload: dict[str, object]) -> dict[str, object]:
    if payload.get("version") and payload.get("installer_download_url"):
        return {
            "version": str(payload.get("version", "") or "").strip(),
            "tag_name": str(payload.get("tag_name", "") or "").strip(),
            "html_url": str(payload.get("html_url", "") or "").strip(),
            "installer_asset_name": str(payload.get("installer_asset_name", "") or "").strip(),
            "installer_download_url": str(payload.get("installer_download_url", "") or "").strip(),
            "installer_size_bytes": _coerce_int(payload.get("installer_size_bytes")) or 0,
        }

    tag_name = str(payload.get("tag_name", "") or "").strip()
    version = _normalize_version(tag_name)
    if not version:
        raise ValueError("Latest release is missing a valid version tag.")

    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise ValueError("Latest release is missing assets.")
    installer_asset = _select_installer_asset(assets, version)
    return {
        "version": version,
        "tag_name": tag_name or f"v{version}",
        "html_url": str(payload.get("html_url", "") or "").strip(),
        "installer_asset_name": str(installer_asset["name"]),
        "installer_download_url": str(installer_asset["browser_download_url"]),
        "installer_size_bytes": _coerce_int(installer_asset.get("size")) or 0,
    }


def _select_installer_asset(
    assets: list[object],
    version: str,
) -> dict[str, object]:
    expected_name = _build_versioned_setup_name(version)
    normalized_assets = [
        asset
        for asset in assets
        if isinstance(asset, dict)
        and str(asset.get("name", "") or "").strip()
        and str(asset.get("browser_download_url", "") or "").strip()
    ]
    for asset in normalized_assets:
        if str(asset.get("name", "") or "").strip() == expected_name:
            return asset
    for asset in normalized_assets:
        name = str(asset.get("name", "") or "").strip().lower()
        if name.startswith("localaicontrolcentersetup-") and name.endswith(".exe"):
            return asset
    raise ValueError("Latest release does not contain a Windows installer asset.")


def _resolve_update_candidate(
    config: ControlCenterConfig,
    latest_release_fetcher,
) -> dict[str, object]:
    current_version = detect_installed_version(config)
    release = latest_release_fetcher()
    latest_version = _normalize_version(str(release.get("version", "") or release.get("tag_name", "") or ""))
    if not latest_version:
        raise ValueError("Latest release version is missing.")
    installer_name = str(release.get("installer_asset_name", "") or "").strip() or _build_versioned_setup_name(latest_version)
    installer_download_url = str(release.get("installer_download_url", "") or "").strip()
    if not installer_download_url:
        raise ValueError("Latest release installer URL is missing.")
    target_path = config.updates_download_root / installer_name
    return {
        "currentVersion": current_version,
        "latestVersion": latest_version,
        "releaseUrl": str(release.get("html_url", "") or "").strip(),
        "targetPath": str(target_path),
        "installerDownloadUrl": installer_download_url,
        "installerSizeBytes": _coerce_int(release.get("installer_size_bytes")) or 0,
        "updateAvailable": _is_newer_version(latest_version, current_version),
    }


def _build_available_update_progress(candidate: dict[str, object]) -> dict[str, object]:
    return {
        "actionId": "",
        "status": "available",
        "phase": "ready-to-download",
        "isActive": False,
        "currentVersion": str(candidate["currentVersion"]),
        "latestVersion": str(candidate["latestVersion"]),
        "releaseUrl": str(candidate["releaseUrl"]),
        "targetPath": str(candidate["targetPath"]),
        "percent": None,
        "downloadedGiB": None,
        "totalGiB": _to_gib(_coerce_int(candidate["installerSizeBytes"])),
        "speedMBps": None,
        "etaSeconds": None,
        "message": f"Dostupan je installer update za verziju {candidate['latestVersion']}.",
        "updatedAt": _utc_now(),
        "workerPid": None,
    }


def _build_up_to_date_progress(
    candidate: dict[str, object],
    *,
    action_id: str = "",
) -> dict[str, object]:
    return {
        "actionId": action_id,
        "status": "up-to-date",
        "phase": "idle",
        "isActive": False,
        "currentVersion": str(candidate["currentVersion"]),
        "latestVersion": str(candidate["latestVersion"]),
        "releaseUrl": str(candidate["releaseUrl"]),
        "targetPath": str(candidate["targetPath"]),
        "percent": None,
        "downloadedGiB": None,
        "totalGiB": None,
        "speedMBps": None,
        "etaSeconds": None,
        "message": f"Već koristiš najnoviju verziju ({candidate['currentVersion']}).",
        "updatedAt": _utc_now(),
        "workerPid": None,
    }


def _build_error_progress(
    config: ControlCenterConfig,
    *,
    current_version: str,
    latest_version: str = "",
    release_url: str = "",
    target_path: str = "",
    message: str,
) -> dict[str, object]:
    return {
        "actionId": "",
        "status": "error",
        "phase": "error",
        "isActive": False,
        "currentVersion": current_version,
        "latestVersion": latest_version,
        "releaseUrl": release_url,
        "targetPath": target_path or str(config.updates_download_root),
        "percent": None,
        "downloadedGiB": None,
        "totalGiB": None,
        "speedMBps": None,
        "etaSeconds": None,
        "message": message,
        "updatedAt": _utc_now(),
        "workerPid": None,
    }


def _write_update_progress(
    config: ControlCenterConfig,
    payload: dict[str, object],
) -> Path:
    return atomic_write_json(
        config.update_progress_path,
        _normalize_update_progress_payload(payload),
    )


def _normalize_update_progress_payload(
    payload: dict[str, object],
) -> dict[str, object]:
    normalized = dict(IDLE_UPDATE_PROGRESS)
    normalized.update(payload)
    normalized["actionId"] = str(normalized.get("actionId", "") or "")
    normalized["status"] = str(normalized.get("status", "idle") or "idle")
    normalized["phase"] = str(normalized.get("phase", "idle") or "idle")
    normalized["isActive"] = bool(normalized.get("isActive", False))
    normalized["currentVersion"] = str(normalized.get("currentVersion", "") or "")
    normalized["latestVersion"] = str(normalized.get("latestVersion", "") or "")
    normalized["releaseUrl"] = str(normalized.get("releaseUrl", "") or "")
    normalized["targetPath"] = str(normalized.get("targetPath", "") or "")
    normalized["percent"] = _coerce_float(normalized.get("percent"))
    normalized["downloadedGiB"] = _coerce_float(normalized.get("downloadedGiB"))
    normalized["totalGiB"] = _coerce_float(normalized.get("totalGiB"))
    normalized["speedMBps"] = _coerce_float(normalized.get("speedMBps"))
    normalized["etaSeconds"] = _coerce_int(normalized.get("etaSeconds"))
    normalized["message"] = str(normalized.get("message", "") or _default_update_message(str(normalized["status"])))
    normalized["updatedAt"] = str(normalized.get("updatedAt", "") or "")
    normalized["workerPid"] = _coerce_int(normalized.get("workerPid"))
    return normalized


def _spawn_update_worker(action_id: str, config: ControlCenterConfig):
    launch_spec = build_worker_launch_spec(
        frozen=bool(getattr(sys, "frozen", False)),
        executable=sys.executable,
        src_root=Path(__file__).resolve().parents[3],
        install_root=config.install_root,
        worker_flag="--update-install-worker",
        worker_module="local_ai_control_center_installer.control_center_backend.workers.update_install_worker",
        worker_args=["--action-id", action_id],
    )
    return subprocess.Popen(
        list(launch_spec.command),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        env=launch_spec.env,
        close_fds=False,
        creationflags=launch_spec.creationflags,
    )


def _launch_installer(installer_path: Path, config: ControlCenterConfig) -> None:
    environment = os.environ.copy()
    environment["LACC_INSTALLER_PREFILL_ROOT"] = str(config.install_root)
    environment["LOCAL_AI_CONTROL_CENTER_INSTALLER_PREFILL_ROOT"] = str(
        config.install_root
    )
    subprocess.Popen(
        [str(installer_path)],
        cwd=str(installer_path.parent),
        env=environment,
        close_fds=False,
        creationflags=new_console_subprocess_creationflags(),
    )


def _is_dead_active_update(payload: dict[str, object]) -> bool:
    if not bool(payload.get("isActive")):
        return False
    status = str(payload.get("status", "") or "")
    if status not in ACTIVE_UPDATE_STATUSES:
        return False
    worker_pid = _coerce_int(payload.get("workerPid"))
    if worker_pid is None:
        return _is_stale_update_snapshot(payload)
    return not _is_process_alive(worker_pid)


def _is_stale_update_snapshot(payload: dict[str, object]) -> bool:
    updated_at = str(payload.get("updatedAt", "") or "")
    if not updated_at:
        return False
    try:
        normalized = updated_at.replace("Z", "+00:00")
        updated_at_dt = datetime.fromisoformat(normalized)
    except ValueError:
        return False
    age_seconds = (datetime.now(timezone.utc) - updated_at_dt.astimezone(timezone.utc)).total_seconds()
    return age_seconds >= UPDATE_PROGRESS_STALE_SECONDS


def _is_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _is_newer_version(latest_version: str, current_version: str) -> bool:
    current_normalized = _normalize_version(current_version)
    if not current_normalized or current_normalized == "unknown":
        return True
    return _numeric_version_key(latest_version) > _numeric_version_key(current_normalized)


def _numeric_version_key(value: str) -> tuple[int, ...]:
    normalized = _normalize_version(value)
    if not normalized:
        return tuple()
    matches = re.findall(r"\d+", normalized)
    if not matches:
        return tuple()
    return tuple(int(part) for part in matches)


def _normalize_version(value: str) -> str:
    normalized = str(value or "").strip()
    if normalized.lower().startswith("v"):
        normalized = normalized[1:].strip()
    return normalized


def _build_versioned_setup_name(version: str) -> str:
    normalized = _normalize_version(version)
    if not normalized:
        raise ValueError("version is required")
    return f"RuntimePilotSetup-v{normalized}.exe"


def _calculate_percent(downloaded_bytes: int, total_bytes: int | None) -> float | None:
    if total_bytes is None or total_bytes <= 0:
        return None
    return round((downloaded_bytes / total_bytes) * 100, 1)


def _to_gib(value: int | None) -> float | None:
    if value is None:
        return None
    return round(value / (1024 ** 3), 2)


def _coerce_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _coerce_eta(value: float | None) -> int | None:
    if value is None:
        return None
    return max(int(round(value)), 0)


def _default_update_message(status: str) -> str:
    return {
        "idle": "Nema aktivnog update toka.",
        "available": "Dostupan je novi installer update.",
        "up-to-date": "Već koristiš najnoviju verziju.",
        "starting": "Pokrećem update worker.",
        "downloading": "Installer download je u toku.",
        "launching-installer": "Installer je preuzet i pokreće se.",
        "completed": "Installer je pokrenut.",
        "error": "Update je prijavio grešku.",
    }.get(status, "Nema aktivnog update toka.")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
