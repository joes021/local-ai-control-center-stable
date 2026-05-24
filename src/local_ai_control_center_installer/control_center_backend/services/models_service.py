from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any
from urllib.parse import quote
from uuid import uuid4

from local_ai_control_center_installer.control_center_backend.config import (
    ControlCenterConfig,
    get_config,
)
from local_ai_control_center_installer.control_center_backend.services.server_service import (
    start_server,
    stop_server,
)
from local_ai_control_center_installer.control_center_backend.services.state_helpers import (
    action_result,
    atomic_write_json,
    build_user_preset_id,
    read_json_object,
    slugify_token,
)
from local_ai_control_center_installer.control_center_backend.services.status_service import (
    classify_runtime_model_support,
    find_runtime_pid,
)
from local_ai_control_center_installer.downloads import (
    DownloadProgress,
    download_file as shared_download_file,
    verify_sha256,
)
from local_ai_control_center_installer.opencode_bootstrap import _write_managed_config
from local_ai_control_center_installer.runtime_bootstrap import (
    _write_active_model_config,
    load_runtime_endpoint_config,
)
from local_ai_control_center_installer.runtime_manifest import (
    list_prompt_starter_models,
    load_runtime_manifest,
)


IDLE_DOWNLOAD_PROGRESS = {
    "actionId": "",
    "status": "idle",
    "isActive": False,
    "modelId": "",
    "fileName": "",
    "source": "",
    "percent": None,
    "downloadedGiB": None,
    "totalGiB": None,
    "speedMBps": None,
    "etaSeconds": None,
    "message": "Nema aktivnog download-a.",
    "updatedAt": "",
    "workerPid": None,
}

DOWNLOAD_PROGRESS_STALE_SECONDS = 120


def load_models_payload(
    config: ControlCenterConfig | None = None,
) -> dict[str, list[dict[str, object]]]:
    config = config or get_config()
    manifest = load_runtime_manifest()
    active_model = _load_active_model_payload(config)
    active_model_id = str(active_model.get("model_id", "") or "")
    model_roots = _load_model_roots(config)
    registry = _load_custom_registry(config)

    entries: list[dict[str, object]] = []
    seen_ids: set[str] = set()

    for option in list_prompt_starter_models(manifest):
        starter_model = manifest["starter_models"][option.model_id]
        entry = _build_curated_model_entry(
            config,
            starter_model,
            active_model_id=active_model_id,
        )
        entries.append(entry)
        seen_ids.add(entry["id"])

    for raw in registry.get("models", []):
        entry = _build_custom_model_entry(
            config,
            raw,
            active_model_id=active_model_id,
            model_roots=model_roots,
        )
        if entry is None:
            continue
        entries = [item for item in entries if item["id"] != entry["id"]]
        entries.append(entry)
        seen_ids.add(entry["id"])

    discovered = _build_discovered_active_entry(
        config,
        active_model,
        active_model_id=active_model_id,
        seen_ids=seen_ids,
    )
    if discovered is not None:
        entries.append(discovered)

    return _group_model_entries(entries)


def activate_model(
    model_id: str,
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    model = _resolve_model_by_id(config, model_id)
    if model is None:
        return action_result("error", "activate-model", f"Model nije pronadjen: {model_id}", stderr=f"Model nije pronadjen: {model_id}")

    model_path = Path(str(model.get("resolvedPath", "") or ""))
    if not model_path.is_file():
        return action_result(
            "error",
            "activate-model",
            f"Model nije prisutan na disku: {model_id}",
            stderr=f"Model nije prisutan na disku: {model_id}",
        )
    model_supported, model_reason = classify_runtime_model_support(
        model_id=str(model["id"]),
        model_path=model_path,
    )
    if not model_supported:
        return action_result(
            "error",
            "activate-model",
            model_reason,
            stderr=model_reason,
        )

    active_model_snapshot = _snapshot_file_contents(config.active_model_config_path)
    managed_config_snapshot = _snapshot_file_contents(config.opencode_managed_config_path)

    def rollback_activation_state() -> None:
        _restore_file_snapshot(config.active_model_config_path, active_model_snapshot)
        _restore_file_snapshot(config.opencode_managed_config_path, managed_config_snapshot)

    _write_active_model_config(
        config.active_model_config_path,
        model_id=str(model["id"]),
        model_path=model_path,
    )

    summary_bits = [f"Aktivan model postavljen na: {model['label']}"]
    try:
        runtime_endpoint = load_runtime_endpoint_config(config.runtime_endpoint_config_path)
        _write_managed_config(
            config.opencode_managed_config_path,
            model_id=str(model["id"]),
            public_model_name=model_path.name,
            base_url=runtime_endpoint.base_url,
        )
        summary_bits.append("OpenCode config je osvezen")
    except Exception as exc:  # noqa: BLE001
        rollback_activation_state()
        return action_result(
            "error",
            "activate-model",
            f"{summary_bits[0]}, ali OpenCode config nije osvezen. Promena aktivnog modela je vracena.",
            stdout=json.dumps(
                {
                    "modelId": model["id"],
                    "modelPath": str(model_path),
                },
                ensure_ascii=False,
            ),
            stderr=str(exc),
        )

    try:
        runtime_endpoint = load_runtime_endpoint_config(config.runtime_endpoint_config_path)
    except Exception:  # noqa: BLE001
        runtime_endpoint = None
    if runtime_endpoint is not None and find_runtime_pid(runtime_endpoint.port) is not None:
        stop_result = stop_server(config)
        if stop_result.get("status") != "ok":
            rollback_activation_state()
            return action_result(
                "error",
                "activate-model",
                f"Runtime nije mogao bezbedno da se zaustavi za promenu modela. Promena aktivnog modela je vracena. {stop_result.get('summary', '')}".strip(),
                stderr=str(stop_result.get("details", {}).get("stderr", "") or stop_result.get("summary", "")),
            )
        start_result = start_server(config)
        if start_result.get("status") != "ok":
            rollback_activation_state()
            restore_result = start_server(config)
            if restore_result.get("status") == "ok":
                return action_result(
                    "error",
                    "activate-model",
                    "Novi model nije mogao da pokrene runtime. Promena aktivnog modela je vracena i prethodni runtime je ponovo pokrenut.",
                    stderr=str(start_result.get("details", {}).get("stderr", "") or start_result.get("summary", "")),
                )
            return action_result(
                "error",
                "activate-model",
                "Novi model nije mogao da pokrene runtime. Promena aktivnog modela je vracena, ali prethodni runtime nije mogao automatski da se vrati.",
                stderr=str(start_result.get("details", {}).get("stderr", "") or start_result.get("summary", "")),
            )
        summary_bits.append("runtime je restartovan")

    return action_result(
        "ok",
        "activate-model",
        ". ".join(summary_bits) + ".",
        stdout=json.dumps(
            {
                "modelId": model["id"],
                "modelPath": str(model_path),
            },
            ensure_ascii=False,
        ),
    )


def add_local_model(
    path: str,
    label: str = "",
    family: str = "Custom",
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    source_path = Path(str(path or "").strip()).expanduser()
    if not source_path.is_file():
        return action_result(
            "error",
            "add-local-model",
            "Lokalni GGUF fajl nije pronadjen.",
            stderr="Lokalni GGUF fajl nije pronadjen.",
        )
    if source_path.suffix.lower() != ".gguf":
        return action_result(
            "error",
            "add-local-model",
            "Lokalni fajl mora da bude .gguf model.",
            stderr="Lokalni fajl mora da bude .gguf model.",
        )

    target_root = config.install_root / "models" / "local"
    target_root.mkdir(parents=True, exist_ok=True)
    target_path = target_root / source_path.name
    shutil.copy2(source_path, target_path)

    entry = {
        "id": _build_local_model_id(source_path.name),
        "label": label.strip() or source_path.stem,
        "filename": source_path.name,
        "family": family.strip() or "Custom",
        "source": "local",
        "description": "Lokalno dodat GGUF model.",
        "absolute_path": str(target_path),
    }
    _upsert_custom_registry_entry(config, entry)
    return action_result(
        "ok",
        "add-local-model",
        f"Lokalni model je dodat: {entry['label']}",
        stdout=str(target_path),
    )


def add_hf_model(
    repo: str,
    filename: str,
    label: str = "",
    family: str = "Custom",
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    normalized_repo = str(repo or "").strip()
    normalized_filename = str(filename or "").strip()
    if not normalized_repo or not normalized_filename:
        return action_result(
            "error",
            "add-hf-model",
            "Repo i filename su obavezni.",
            stderr="Repo i filename su obavezni.",
        )

    entry = {
        "id": _build_remote_model_id("huggingface", normalized_repo, normalized_filename),
        "label": label.strip() or Path(normalized_filename).stem,
        "filename": Path(normalized_filename).name,
        "family": family.strip() or "Custom",
        "source": "huggingface",
        "repo": normalized_repo,
        "description": "Hugging Face model dodat u lokalni katalog.",
        "download_url": _build_huggingface_download_url(normalized_repo, normalized_filename),
    }
    _upsert_custom_registry_entry(config, entry)
    result = action_result(
        "ok",
        "add-hf-model",
        f"Hugging Face model je dodat u spisak: {entry['label']}. Sledeci korak je Download.",
    )
    result["localModelId"] = entry["id"]
    return result


def add_unsloth_model(
    repo: str,
    filename: str,
    label: str = "",
    family: str = "Unsloth",
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    normalized_repo = str(repo or "").strip()
    normalized_filename = str(filename or "").strip()
    if not normalized_repo or not normalized_filename:
        return action_result(
            "error",
            "add-unsloth-model",
            "Repo i filename su obavezni.",
            stderr="Repo i filename su obavezni.",
        )

    entry = {
        "id": _build_remote_model_id("unsloth", normalized_repo, normalized_filename),
        "label": label.strip() or Path(normalized_filename).stem,
        "filename": Path(normalized_filename).name,
        "family": family.strip() or "Unsloth",
        "source": "unsloth",
        "repo": normalized_repo,
        "description": "Unsloth model dodat u lokalni katalog.",
        "download_url": _build_huggingface_download_url(normalized_repo, normalized_filename),
    }
    _upsert_custom_registry_entry(config, entry)
    result = action_result(
        "ok",
        "add-unsloth-model",
        f"Unsloth model je dodat u spisak: {entry['label']}. Sledeci korak je Download.",
    )
    result["localModelId"] = entry["id"]
    return result


def delete_model(
    model_id: str,
    *,
    remove_file: bool = True,
    remove_registry: bool = True,
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    model = _resolve_model_by_id(config, model_id)
    if model is None:
        return action_result("error", "delete-model", f"Model nije pronadjen: {model_id}", stderr=f"Model nije pronadjen: {model_id}")
    if not remove_file and not remove_registry:
        return action_result("error", "delete-model", "Izaberi bar jednu delete akciju.", stderr="Izaberi bar jednu delete akciju.")

    active_model = _load_active_model_payload(config)
    if remove_file and str(active_model.get("model_id", "") or "") == model_id:
        return action_result(
            "error",
            "delete-model",
            "Aktivni model ne moze da se obrise sa diska dok je aktivan.",
            stderr="Aktivni model ne moze da se obrise sa diska dok je aktivan.",
        )

    removed_file = False
    removed_registry = False
    model_path = Path(str(model.get("resolvedPath", "") or ""))
    if remove_file and model_path.is_file():
        model_path.unlink()
        removed_file = True

    if remove_registry and bool(model.get("isCustom")):
        removed_registry = _remove_custom_registry_entry(config, model_id)

    summary_bits: list[str] = []
    if remove_file:
        summary_bits.append("fajl obrisan sa diska" if removed_file else "fajl nije postojao")
    if remove_registry:
        if bool(model.get("isCustom")):
            summary_bits.append("uklonjen iz kataloga" if removed_registry else "nije nadjen u katalogu")
        else:
            summary_bits.append("kurirani modeli ostaju u katalogu")

    return action_result(
        "ok",
        "delete-model",
        f"{model_id}: {', '.join(summary_bits) or 'nije bilo promena'}",
        stdout=json.dumps(
            {
                "modelId": model_id,
                "removedFile": removed_file,
                "removedRegistry": removed_registry,
                "path": str(model_path),
            },
            ensure_ascii=False,
        ),
    )


def download_model(
    model_id: str,
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    current_progress = load_download_progress_payload(config)
    if current_progress["isActive"]:
        return action_result(
            "error",
            "download-model",
            "Vec postoji aktivan model download. Sacekaj da se zavrsi pre novog pokusaja.",
            stderr="Vec postoji aktivan model download.",
        )

    model = _resolve_model_by_id(config, model_id)
    if model is None:
        return action_result("error", "download-model", f"Model nije pronadjen: {model_id}", stderr=f"Model nije pronadjen: {model_id}")
    if bool(model.get("installed")):
        _write_download_progress(
            config,
            {
                **IDLE_DOWNLOAD_PROGRESS,
                "status": "already-installed",
                "modelId": model_id,
                "fileName": str(model.get("filename", "") or ""),
                "source": str(model.get("source", "") or ""),
                "message": "Model je vec prisutan na disku.",
                "updatedAt": _utc_now(),
            },
        )
        return action_result("ok", "download-model", "Model je vec prisutan na disku.")
    if str(model.get("source", "")) == "local":
        return action_result(
            "error",
            "download-model",
            "Lokalni modeli se ne skidaju ponovo; dodaj ih kroz lokalni GGUF import.",
            stderr="Lokalni modeli se ne skidaju ponovo.",
        )

    action_id = _build_model_action_id()
    _write_model_action_state(
        config,
        action_id,
        {
            "actionId": action_id,
            "status": "accepted",
            "summary": f"Download je pokrenut za: {model.get('label', model_id)}",
            "isDone": False,
            "result": action_result(
                "accepted",
                "download-model",
                f"Download je pokrenut za: {model.get('label', model_id)}",
                action_id=action_id,
            ),
        },
    )
    _write_download_progress(
        config,
        {
            **IDLE_DOWNLOAD_PROGRESS,
            "actionId": action_id,
            "status": "starting",
            "isActive": True,
            "modelId": model_id,
            "fileName": str(model.get("filename", "") or ""),
            "source": str(model.get("source", "") or ""),
            "message": f"Pokrecem download za {model.get('label', model_id)}",
            "updatedAt": _utc_now(),
        },
    )
    try:
        process = _spawn_model_download_worker(model_id, config)
    except Exception as exc:  # noqa: BLE001
        failure = action_result(
            "error",
            "download-model",
            f"Pokretanje model download worker-a nije uspelo: {exc}",
            stderr=str(exc),
        )
        _write_model_action_state(
            config,
            action_id,
            {
                "actionId": action_id,
                "status": "error",
                "summary": str(failure["summary"]),
                "isDone": True,
                "result": failure,
            },
        )
        _write_download_progress(
            config,
            {
                **IDLE_DOWNLOAD_PROGRESS,
                "actionId": action_id,
                "status": "error",
                "modelId": model_id,
                "fileName": str(model.get("filename", "") or ""),
                "source": str(model.get("source", "") or ""),
                "message": str(failure["summary"]),
                "updatedAt": _utc_now(),
            },
        )
        return failure
    return action_result(
        "accepted",
        "download-model",
        f"Download je pokrenut za: {model.get('label', model_id)}",
        action_id=action_id,
        stdout=json.dumps({"pid": getattr(process, "pid", None)}, ensure_ascii=False),
    )


def run_model_download_worker(
    model_id: str,
    *,
    config: ControlCenterConfig | None = None,
    download_file=shared_download_file,
) -> dict[str, object]:
    config = config or get_config()
    current_progress = load_download_progress_payload(config)
    action_id = str(current_progress.get("actionId", "") or "")
    model = _resolve_model_by_id(config, model_id)
    if model is None:
        failure = action_result("error", "download-model", f"Model nije pronadjen: {model_id}", stderr=f"Model nije pronadjen: {model_id}")
        _write_download_progress(
            config,
            {
                **IDLE_DOWNLOAD_PROGRESS,
                "actionId": action_id,
                "status": "error",
                "modelId": model_id,
                "message": str(failure["summary"]),
                "updatedAt": _utc_now(),
            },
        )
        _finalize_model_action_state(config, action_id, failure)
        return failure

    source = str(model.get("source", "") or "")
    filename = str(model.get("filename", "") or "")
    url = str(model.get("downloadUrl", "") or "")
    destination = Path(str(model.get("downloadPath", "") or ""))
    expected_sha256 = str(model.get("sha256", "") or "").strip().lower()
    if not url or not destination:
        failure = action_result(
            "error",
            "download-model",
            f"Model nema validan download izvor: {model_id}",
            stderr="Model nema validan download izvor.",
        )
        _write_download_progress(
            config,
            {
                **IDLE_DOWNLOAD_PROGRESS,
                "actionId": action_id,
                "status": "error",
                "modelId": model_id,
                "fileName": filename,
                "source": source,
                "message": str(failure["summary"]),
                "updatedAt": _utc_now(),
            },
        )
        _finalize_model_action_state(config, action_id, failure)
        return failure

    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_destination = destination.with_suffix(destination.suffix + ".download")
    start_time = time.monotonic()

    def progress_callback(progress: DownloadProgress) -> None:
        elapsed = max(time.monotonic() - start_time, 0.0)
        speed_mb = None
        if elapsed > 0 and progress.bytes_downloaded > 0:
            speed_mb = round(progress.bytes_downloaded / elapsed / (1024 * 1024), 1)
        total_gib = _to_gib(progress.total_bytes)
        downloaded_gib = _to_gib(progress.bytes_downloaded)
        percent = None
        if progress.total_bytes:
            percent = round((progress.bytes_downloaded / progress.total_bytes) * 100, 1)
        _write_download_progress(
            config,
            {
                "actionId": action_id,
                "status": "downloading",
                "isActive": True,
                "modelId": model_id,
                "fileName": filename,
                "source": source,
                "percent": percent,
                "downloadedGiB": downloaded_gib,
                "totalGiB": total_gib,
                "speedMBps": speed_mb,
                "etaSeconds": _coerce_eta(progress.eta_seconds),
                "message": f"Download je u toku za {model.get('label', model_id)}",
                "updatedAt": _utc_now(),
                "workerPid": os.getpid(),
            },
        )

    try:
        download_file(url, temp_destination, progress_callback=progress_callback)
        if expected_sha256 and not verify_sha256(temp_destination, expected_sha256):
            raise ValueError("Checksum verifikacija modela nije prosla.")
        temp_destination.replace(destination)
        _update_custom_model_installed_path(config, model_id, destination)
        _write_download_progress(
            config,
            {
                "actionId": action_id,
                "status": "completed",
                "isActive": False,
                "modelId": model_id,
                "fileName": filename,
                "source": source,
                "percent": 100.0,
                "downloadedGiB": _to_gib(destination.stat().st_size),
                "totalGiB": _to_gib(destination.stat().st_size),
                "speedMBps": None,
                "etaSeconds": 0,
                "message": f"Download je zavrsen za {model.get('label', model_id)}",
                "updatedAt": _utc_now(),
                "workerPid": os.getpid(),
            },
        )
        result = action_result(
            "ok",
            "download-model",
            f"Download je zavrsen za: {model.get('label', model_id)}",
            stdout=str(destination),
        )
        _finalize_model_action_state(config, action_id, result)
        return result
    except Exception as exc:  # noqa: BLE001
        try:
            temp_destination.unlink(missing_ok=True)
        except OSError:
            pass
        _write_download_progress(
            config,
            {
                **IDLE_DOWNLOAD_PROGRESS,
                "actionId": action_id,
                "status": "error",
                "modelId": model_id,
                "fileName": filename,
                "source": source,
                "message": str(exc),
                "updatedAt": _utc_now(),
            },
        )
        result = action_result(
            "error",
            "download-model",
            str(exc),
            stderr=str(exc),
        )
        _finalize_model_action_state(config, action_id, result)
        return result


def load_download_progress_payload(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    payload = read_json_object(config.model_download_progress_path)
    if not payload:
        return dict(IDLE_DOWNLOAD_PROGRESS)

    status = str(payload.get("status", "idle") or "idle")
    normalized = {
        "actionId": str(payload.get("actionId", "") or ""),
        "status": status,
        "isActive": bool(payload.get("isActive", False)),
        "modelId": str(payload.get("modelId", "") or ""),
        "fileName": str(payload.get("fileName", "") or ""),
        "source": str(payload.get("source", "") or ""),
        "percent": _coerce_float(payload.get("percent")),
        "downloadedGiB": _coerce_float(payload.get("downloadedGiB")),
        "totalGiB": _coerce_float(payload.get("totalGiB")),
        "speedMBps": _coerce_float(payload.get("speedMBps")),
        "etaSeconds": _coerce_int(payload.get("etaSeconds")),
        "message": str(payload.get("message", "") or _default_download_message(status)),
        "updatedAt": str(payload.get("updatedAt", "") or ""),
        "workerPid": _coerce_int(payload.get("workerPid")),
    }
    if _is_stale_active_download(normalized):
        stale_message = "Download worker vise nije aktivan. Pokreni download ponovo."
        normalized = {
            **normalized,
            "status": "error",
            "isActive": False,
            "speedMBps": None,
            "etaSeconds": None,
            "message": stale_message,
            "workerPid": None,
        }
        _write_download_progress(config, normalized)
        if normalized["actionId"]:
            _write_model_action_state(
                config,
                str(normalized["actionId"]),
                {
                    "actionId": str(normalized["actionId"]),
                    "status": "error",
                    "summary": stale_message,
                    "isDone": True,
                    "result": action_result(
                        "error",
                        "download-model",
                        stale_message,
                        action_id=str(normalized["actionId"]),
                        stderr=stale_message,
                    ),
                },
            )
    return normalized


def get_model_action_status(
    action_id: str,
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    payload = read_json_object(config.model_action_state_root / f"{action_id}.json")
    if not payload:
        return {
            "actionId": action_id,
            "status": "missing",
            "summary": "Model akcija nije pronadjena.",
            "isDone": True,
            "result": None,
        }
    return {
        "actionId": action_id,
        "status": str(payload.get("status", "missing") or "missing"),
        "summary": str(payload.get("summary", "") or ""),
        "isDone": bool(payload.get("isDone", False)),
        "result": payload.get("result"),
    }


def _build_model_action_id() -> str:
    return f"model-action-{uuid4().hex[:10]}"


def _write_model_action_state(
    config: ControlCenterConfig,
    action_id: str,
    payload: dict[str, object],
) -> None:
    if not action_id:
        return
    atomic_write_json(
        config.model_action_state_root / f"{action_id}.json",
        {
            "actionId": action_id,
            "status": str(payload.get("status", "missing") or "missing"),
            "summary": str(payload.get("summary", "") or ""),
            "isDone": bool(payload.get("isDone", False)),
            "result": payload.get("result"),
        },
    )


def _finalize_model_action_state(
    config: ControlCenterConfig,
    action_id: str,
    result: dict[str, object],
) -> None:
    if not action_id:
        return
    _write_model_action_state(
        config,
        action_id,
        {
            "actionId": action_id,
            "status": str(result.get("status", "missing") or "missing"),
            "summary": str(result.get("summary", "") or ""),
            "isDone": True,
            "result": result,
        },
    )


def _snapshot_file_contents(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, ""
    return True, path.read_text(encoding="utf-8")


def _restore_file_snapshot(path: Path, snapshot: tuple[bool, str]) -> None:
    existed, contents = snapshot
    if not existed:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def _spawn_model_download_worker(model_id: str, config: ControlCenterConfig):
    environment = os.environ.copy()
    if bool(getattr(sys, "frozen", False)):
        command = [
            sys.executable,
            "--model-download-worker",
            "--install-root",
            str(config.install_root),
            "--model-id",
            model_id,
        ]
    else:
        src_root = Path(__file__).resolve().parents[3]
        existing_python_path = environment.get("PYTHONPATH", "").strip()
        environment["PYTHONPATH"] = (
            f"{src_root};{existing_python_path}" if existing_python_path else str(src_root)
        )
        command = [
            sys.executable,
            "-m",
            "local_ai_control_center_installer.control_center_backend.workers.model_download_worker",
            "--install-root",
            str(config.install_root),
            "--model-id",
            model_id,
        ]
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        env=environment,
        close_fds=False,
        creationflags=creation_flags,
    )


def _load_custom_registry(config: ControlCenterConfig) -> dict[str, list[dict[str, object]]]:
    payload = read_json_object(config.custom_models_registry_path)
    models = payload.get("models")
    if not isinstance(models, list):
        return {"models": []}
    return {
        "models": [item for item in models if isinstance(item, dict)],
    }


def _write_custom_registry(
    config: ControlCenterConfig,
    models: list[dict[str, object]],
) -> Path:
    return atomic_write_json(config.custom_models_registry_path, {"models": models})


def _upsert_custom_registry_entry(
    config: ControlCenterConfig,
    entry: dict[str, object],
) -> None:
    registry = _load_custom_registry(config)
    models = [
        item
        for item in registry["models"]
        if str(item.get("id", "") or "") != str(entry.get("id", "") or "")
    ]
    models.append(entry)
    _write_custom_registry(config, models)


def _remove_custom_registry_entry(
    config: ControlCenterConfig,
    model_id: str,
) -> bool:
    registry = _load_custom_registry(config)
    filtered = [
        item
        for item in registry["models"]
        if str(item.get("id", "") or "") != model_id
    ]
    if len(filtered) == len(registry["models"]):
        return False
    _write_custom_registry(config, filtered)
    return True


def _update_custom_model_installed_path(
    config: ControlCenterConfig,
    model_id: str,
    installed_path: Path,
) -> None:
    registry = _load_custom_registry(config)
    updated = False
    for item in registry["models"]:
        if str(item.get("id", "") or "") != model_id:
            continue
        item["absolute_path"] = str(installed_path)
        updated = True
    if updated:
        _write_custom_registry(config, registry["models"])


def _load_active_model_payload(config: ControlCenterConfig) -> dict[str, Any]:
    return read_json_object(config.active_model_config_path)


def _load_model_roots(config: ControlCenterConfig) -> list[Path]:
    payload = read_json_object(config.install_root / "config" / "model-locations.json")
    roots: list[Path] = []
    default_root = str(payload.get("default_model_root", "") or "").strip()
    if default_root:
        roots.append(Path(default_root))
    additional = payload.get("additional_read_only_model_paths")
    if isinstance(additional, list):
        for raw_path in additional:
            if isinstance(raw_path, str) and raw_path.strip():
                roots.append(Path(raw_path))
    roots.append(config.install_root / "models")
    return roots


def _resolve_model_by_id(
    config: ControlCenterConfig,
    model_id: str,
) -> dict[str, object] | None:
    payload = load_models_payload(config)
    for group in ("curated", "local", "huggingFace", "unsloth"):
        for item in payload[group]:
            if str(item.get("id", "") or "") == model_id:
                return item
    return None


def _build_curated_model_entry(
    config: ControlCenterConfig,
    starter_model: dict[str, Any],
    *,
    active_model_id: str,
) -> dict[str, object]:
    install_subdir = starter_model["install_subdir"]
    target_filename = starter_model["target_filename"]
    path = config.install_root / install_subdir / target_filename
    size_bytes = starter_model.get("size_bytes")
    free_disk_gib = _get_free_disk_gib(path.parent)
    needed_gib = _to_gib(max((size_bytes or 0) - (path.stat().st_size if path.is_file() else 0), 0))
    return {
        "id": str(starter_model["id"]),
        "label": str(starter_model.get("prompt_label", starter_model["id"])),
        "source": "curated",
        "active": str(starter_model["id"]) == active_model_id,
        "installed": path.is_file(),
        "filename": target_filename,
        "family": _infer_model_family(target_filename),
        "description": "Kurirani installer-managed starter model.",
        "isCustom": False,
        "mtpStatus": _classify_mtp_status("curated", target_filename, ""),
        "mtpStatusLabel": _mtp_label(_classify_mtp_status("curated", target_filename, "")),
        "approxSizeGiB": _to_gib(size_bytes),
        "minimumGpuMiB": _infer_minimum_gpu_mib(str(starter_model["id"])),
        "recommendedGpuMiB": _infer_recommended_gpu_mib(str(starter_model["id"])),
        "minimumRamGiB": _infer_minimum_ram_gib(str(starter_model["id"])),
        "installedSizeGiB": _to_gib(path.stat().st_size if path.is_file() else None),
        "diskNeededGiB": needed_gib,
        "freeDiskGiB": free_disk_gib,
        "hasEnoughDisk": None if free_disk_gib is None or needed_gib is None else free_disk_gib >= needed_gib,
        "resolvedPath": str(path),
        "downloadPath": str(path),
        "downloadUrl": str(starter_model["url"]),
        "sha256": str(starter_model.get("sha256", "") or ""),
    }


def _build_custom_model_entry(
    config: ControlCenterConfig,
    raw: dict[str, Any],
    *,
    active_model_id: str,
    model_roots: list[Path],
) -> dict[str, object] | None:
    source = _normalize_custom_source(str(raw.get("source", "") or raw.get("customSource", "") or "local"))
    filename = str(raw.get("filename", "") or "").strip()
    model_id = str(raw.get("id", "") or "").strip()
    if not model_id or not filename:
        return None
    resolved_path = _resolve_custom_model_path(config, raw, model_roots)
    installed = resolved_path.is_file() if resolved_path is not None else False
    installed_size = resolved_path.stat().st_size if installed and resolved_path is not None else None
    download_path = _resolve_custom_download_path(config, source, raw, filename)
    free_disk_gib = _get_free_disk_gib(download_path.parent)
    return {
        "id": model_id,
        "label": str(raw.get("label", "") or Path(filename).stem),
        "source": "huggingface" if source == "huggingface" else source,
        "active": model_id == active_model_id,
        "installed": installed,
        "filename": filename,
        "family": str(raw.get("family", "") or _infer_model_family(filename)),
        "description": str(raw.get("description", "") or ""),
        "isCustom": True,
        "mtpStatus": _classify_mtp_status(source, filename, str(raw.get("repo", "") or "")),
        "mtpStatusLabel": _mtp_label(_classify_mtp_status(source, filename, str(raw.get("repo", "") or ""))),
        "approxSizeGiB": _to_gib(_coerce_int(raw.get("size_bytes"))),
        "minimumGpuMiB": _coerce_int(raw.get("minimumGpuMiB")),
        "recommendedGpuMiB": _coerce_int(raw.get("recommendedGpuMiB")),
        "minimumRamGiB": _coerce_float(raw.get("minimumRamGiB")),
        "installedSizeGiB": _to_gib(installed_size),
        "diskNeededGiB": _to_gib(max((_coerce_int(raw.get("size_bytes")) or 0) - (installed_size or 0), 0)),
        "freeDiskGiB": free_disk_gib,
        "hasEnoughDisk": None,
        "resolvedPath": str(resolved_path) if resolved_path is not None else "",
        "downloadPath": str(download_path),
        "downloadUrl": str(raw.get("download_url", "") or ""),
        "sha256": str(raw.get("sha256", "") or ""),
        "repo": str(raw.get("repo", "") or ""),
    }


def _build_discovered_active_entry(
    config: ControlCenterConfig,
    active_model: dict[str, Any],
    *,
    active_model_id: str,
    seen_ids: set[str],
) -> dict[str, object] | None:
    model_path = Path(str(active_model.get("model_path", "") or "")).expanduser()
    if not model_path.is_file():
        return None
    discovered_id = str(active_model_id or model_path.name)
    if discovered_id in seen_ids:
        return None
    return {
        "id": discovered_id,
        "label": model_path.name,
        "source": "local",
        "active": True,
        "installed": True,
        "filename": model_path.name,
        "family": _infer_model_family(model_path.name),
        "description": "Detektovan iz installer-managed active-model konfiguracije.",
        "isCustom": True,
        "mtpStatus": _classify_mtp_status("local", model_path.name, ""),
        "mtpStatusLabel": _mtp_label(_classify_mtp_status("local", model_path.name, "")),
        "approxSizeGiB": _to_gib(model_path.stat().st_size),
        "minimumGpuMiB": None,
        "recommendedGpuMiB": None,
        "minimumRamGiB": None,
        "installedSizeGiB": _to_gib(model_path.stat().st_size),
        "diskNeededGiB": 0.0,
        "freeDiskGiB": _get_free_disk_gib(model_path.parent),
        "hasEnoughDisk": True,
        "resolvedPath": str(model_path),
        "downloadPath": "",
        "downloadUrl": "",
        "sha256": "",
    }


def _group_model_entries(entries: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    payload = {
        "curated": [],
        "local": [],
        "huggingFace": [],
        "unsloth": [],
    }
    for entry in sorted(entries, key=lambda item: (str(item["label"]).lower(), str(item["id"]).lower())):
        source = str(entry.get("source", "curated") or "curated")
        if source == "unsloth":
            payload["unsloth"].append(entry)
        elif source == "huggingface":
            payload["huggingFace"].append(entry)
        elif source == "local":
            payload["local"].append(entry)
        else:
            payload["curated"].append(entry)
    return payload


def _resolve_custom_model_path(
    config: ControlCenterConfig,
    raw: dict[str, Any],
    model_roots: list[Path],
) -> Path | None:
    explicit_path = str(raw.get("absolute_path", "") or raw.get("absolutePath", "") or "").strip()
    if explicit_path:
        explicit = Path(explicit_path).expanduser()
        if explicit.is_file():
            return explicit
    filename = str(raw.get("filename", "") or "").strip()
    if not filename:
        return None
    for root in model_roots:
        candidate = root / filename
        if candidate.is_file():
            return candidate
    source = _normalize_custom_source(str(raw.get("source", "") or raw.get("customSource", "") or "local"))
    download_path = _resolve_custom_download_path(config, source, raw, filename)
    if download_path.is_file():
        return download_path
    return None


def _resolve_custom_download_path(
    config: ControlCenterConfig,
    source: str,
    raw: dict[str, Any],
    filename: str,
) -> Path:
    if source == "local":
        absolute_path = str(raw.get("absolute_path", "") or raw.get("absolutePath", "") or "").strip()
        if absolute_path:
            return Path(absolute_path).expanduser()
        return config.install_root / "models" / "local" / Path(filename).name

    repo = str(raw.get("repo", "") or "").strip()
    repo_slug = slugify_token(repo.replace("/", "-"), fallback=source)
    return config.install_root / "models" / source / repo_slug / Path(filename).name


def _build_huggingface_download_url(repo: str, filename: str) -> str:
    encoded_segments = [quote(segment, safe="-._") for segment in Path(filename).parts]
    return f"https://huggingface.co/{repo}/resolve/main/{'/'.join(encoded_segments)}"


def _build_local_model_id(filename: str) -> str:
    return f"local-{slugify_token(Path(filename).stem, fallback='model')}"


def _build_remote_model_id(source: str, repo: str, filename: str) -> str:
    return (
        f"{source}-{slugify_token(repo.replace('/', '-'), fallback=source)}-"
        f"{slugify_token(Path(filename).stem, fallback='model')}"
    )


def _normalize_custom_source(value: str) -> str:
    lowered = str(value or "").strip().lower()
    if lowered in {"hf", "hugging-face", "huggingface"}:
        return "huggingface"
    if lowered == "unsloth":
        return "unsloth"
    return "local"


def _write_download_progress(
    config: ControlCenterConfig,
    payload: dict[str, object],
) -> None:
    previous = read_json_object(config.model_download_progress_path)
    atomic_write_json(
        config.model_download_progress_path,
        _merge_download_progress_payload(previous, payload),
    )


def _merge_download_progress_payload(
    previous: dict[str, object],
    incoming: dict[str, object],
) -> dict[str, object]:
    if not _is_same_active_download(previous, incoming):
        return incoming

    merged = dict(incoming)
    previous_status = str(previous.get("status", "") or "")
    incoming_status = str(incoming.get("status", "") or "")
    if previous_status == "downloading" and incoming_status == "starting":
        merged["status"] = "downloading"
    merged["actionId"] = str(incoming.get("actionId", "") or previous.get("actionId", "") or "")
    merged["workerPid"] = _coerce_int(incoming.get("workerPid")) or _coerce_int(previous.get("workerPid"))

    merged["percent"] = _prefer_non_regressing_number(
        previous.get("percent"),
        incoming.get("percent"),
    )
    merged["downloadedGiB"] = _prefer_non_regressing_number(
        previous.get("downloadedGiB"),
        incoming.get("downloadedGiB"),
    )
    merged["totalGiB"] = _prefer_non_regressing_number(
        previous.get("totalGiB"),
        incoming.get("totalGiB"),
    )
    merged["speedMBps"] = _prefer_existing_number(
        previous.get("speedMBps"),
        incoming.get("speedMBps"),
    )
    merged["etaSeconds"] = _prefer_existing_number(
        previous.get("etaSeconds"),
        incoming.get("etaSeconds"),
    )
    return merged


def _is_same_active_download(
    previous: dict[str, object],
    incoming: dict[str, object],
) -> bool:
    if not isinstance(previous, dict) or not isinstance(incoming, dict):
        return False
    if not bool(previous.get("isActive")) or not bool(incoming.get("isActive")):
        return False
    previous_status = str(previous.get("status", "") or "")
    incoming_status = str(incoming.get("status", "") or "")
    if previous_status not in {"starting", "downloading"}:
        return False
    if incoming_status not in {"starting", "downloading"}:
        return False
    previous_model = str(previous.get("modelId", "") or "")
    incoming_model = str(incoming.get("modelId", "") or "")
    if not previous_model or previous_model != incoming_model:
        return False
    previous_source = str(previous.get("source", "") or "")
    incoming_source = str(incoming.get("source", "") or "")
    return previous_source == incoming_source


def _prefer_non_regressing_number(previous: object, incoming: object) -> object:
    previous_number = _coerce_float(previous)
    incoming_number = _coerce_float(incoming)
    if incoming_number is None:
        return previous_number
    if previous_number is None:
        return incoming_number
    return incoming_number if incoming_number >= previous_number else previous_number


def _prefer_existing_number(previous: object, incoming: object) -> object:
    incoming_number = _coerce_float(incoming)
    if incoming_number is not None:
        return incoming_number
    return _coerce_float(previous)


def _is_stale_active_download(payload: dict[str, object]) -> bool:
    if not bool(payload.get("isActive")):
        return False
    status = str(payload.get("status", "") or "")
    if status not in {"starting", "downloading"}:
        return False
    updated_at = str(payload.get("updatedAt", "") or "")
    if not updated_at:
        return False
    try:
        normalized = updated_at.replace("Z", "+00:00")
        updated_at_dt = datetime.fromisoformat(normalized)
    except ValueError:
        return False
    age_seconds = (datetime.now(timezone.utc) - updated_at_dt.astimezone(timezone.utc)).total_seconds()
    return age_seconds >= DOWNLOAD_PROGRESS_STALE_SECONDS


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_download_message(status: str) -> str:
    return {
        "starting": "Download se priprema.",
        "downloading": "Download je u toku.",
        "completed": "Download je zavrsen.",
        "already-installed": "Model je vec instaliran.",
        "error": "Download je prijavio gresku.",
    }.get(status, "Nema aktivnog download-a.")


def _get_free_disk_gib(path: Path) -> float | None:
    try:
        usage = shutil.disk_usage(path if path.exists() else path.parent)
    except OSError:
        return None
    return round(usage.free / (1024 ** 3), 2)


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


def _infer_model_family(filename: str) -> str:
    lowered = filename.lower()
    if "qwen" in lowered:
        return "Qwen"
    if "gemma" in lowered:
        return "Gemma"
    if "mistral" in lowered:
        return "Mistral"
    if "deepseek" in lowered:
        return "DeepSeek"
    if "llama" in lowered:
        return "Llama"
    return "Custom"


def _classify_mtp_status(source: str, filename: str, repo: str) -> str:
    joined = f"{source} {filename} {repo}".lower()
    if "mtp" in joined:
        return "has-mtp"
    if source == "unsloth":
        return "no-mtp"
    return "unknown"


def _mtp_label(status: str) -> str:
    return {
        "no-mtp": "bez MTP",
        "has-mtp": "ima MTP",
        "unknown": "nepoznato",
    }.get(status, "nepoznato")


def _infer_minimum_gpu_mib(model_id: str) -> int | None:
    return {
        "recommended-6gb": 6144,
        "recommended-12gb": 12288,
        "recommended-24gb": 24576,
    }.get(model_id)


def _infer_recommended_gpu_mib(model_id: str) -> int | None:
    return {
        "recommended-6gb": 8192,
        "recommended-12gb": 16384,
        "recommended-24gb": 24576,
    }.get(model_id)


def _infer_minimum_ram_gib(model_id: str) -> float | None:
    return {
        "recommended-6gb": 12.0,
        "recommended-12gb": 24.0,
        "recommended-24gb": 48.0,
    }.get(model_id)
