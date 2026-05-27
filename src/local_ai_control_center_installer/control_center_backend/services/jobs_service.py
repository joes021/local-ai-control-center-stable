from __future__ import annotations

from datetime import UTC, datetime, timedelta
import threading
import time
from typing import Any, Callable
from uuid import uuid4

from local_ai_control_center_installer.control_center_backend.config import ControlCenterConfig, get_config
from local_ai_control_center_installer.control_center_backend.services.benchmark_service import (
    load_benchmark_summary,
    start_battery_benchmark,
)
from local_ai_control_center_installer.control_center_backend.services.fleet_service import (
    load_fleet_summary,
    refresh_fleet_machine,
)
from local_ai_control_center_installer.control_center_backend.services.observability_service import (
    load_observability_payload,
)
from local_ai_control_center_installer.control_center_backend.services.settings_service import (
    load_workflow_presets,
)
from local_ai_control_center_installer.control_center_backend.services.state_helpers import (
    action_result,
    atomic_write_json,
    read_json_object,
    slugify_token,
)
from local_ai_control_center_installer.control_center_backend.services.status_service import (
    load_status_payload,
)
from local_ai_control_center_installer.control_center_backend.services.updates_service import (
    check_for_updates,
)


DEFAULT_INTERVAL_MINUTES = 60
MIN_INTERVAL_MINUTES = 5
MAX_INTERVAL_MINUTES = 24 * 60
SCHEDULER_POLL_SECONDS = 30.0

JOB_KIND_SPECS = [
    {
        "id": "health-check",
        "label": "Health check",
        "summary": "Hvata runtime, server i observability snapshot bez menjanja aktivnog modela.",
    },
    {
        "id": "update-check",
        "label": "Update check",
        "summary": "Periodicno proverava da li postoji noviji installer release.",
    },
    {
        "id": "fleet-refresh",
        "label": "Fleet refresh",
        "summary": "Osvezava sve dodate remote mašine i njihov token flow snapshot.",
    },
    {
        "id": "benchmark-battery",
        "label": "Benchmark battery",
        "summary": "Pokreće trenutno izabranu benchmark battery sekvencu.",
    },
    {
        "id": "workflow-pulse",
        "label": "Workflow pulse",
        "summary": "Snima aktivni workflow preset i glavni search/knowledge pravac za kasniji radni ritam.",
    },
]
ALLOWED_JOB_KINDS = {item["id"] for item in JOB_KIND_SPECS}
_SCHEDULER_LOCK = threading.Lock()
_SCHEDULER_THREAD: threading.Thread | None = None
_SCHEDULER_STOP = threading.Event()


def load_jobs_summary(config: ControlCenterConfig | None = None) -> dict[str, object]:
    resolved_config = config or get_config()
    jobs = _load_jobs(resolved_config)
    return {
        "generatedAt": _now_iso(),
        "jobCount": len(jobs),
        "jobs": jobs,
        "availableKinds": JOB_KIND_SPECS,
    }


def save_job(payload: dict[str, object], config: ControlCenterConfig | None = None) -> dict[str, object]:
    resolved_config = config or get_config()
    jobs = _load_jobs(resolved_config)
    normalized = _normalize_job_payload(payload, existing=None)

    existing_index = next(
        (index for index, item in enumerate(jobs) if item.get("id") == normalized["id"]),
        None,
    )
    if existing_index is None:
        jobs.append(normalized)
        summary = f"Job {normalized['name']} je sačuvan."
    else:
        previous = jobs[existing_index]
        normalized["lastRunAt"] = previous.get("lastRunAt", "")
        normalized["lastStatus"] = previous.get("lastStatus", "idle")
        normalized["lastSummary"] = previous.get("lastSummary", "")
        normalized["lastDetails"] = previous.get("lastDetails", {})
        jobs[existing_index] = normalized
        summary = f"Job {normalized['name']} je azuriran."

    _save_jobs(resolved_config, jobs)
    return {
        "status": "ok",
        "summary": summary,
        "job": normalized,
    }


def delete_job(job_id: str, config: ControlCenterConfig | None = None) -> dict[str, object]:
    resolved_config = config or get_config()
    jobs = _load_jobs(resolved_config)
    filtered = [job for job in jobs if job.get("id") != job_id]
    if len(filtered) == len(jobs):
        return action_result("error", "delete-job", f"Job {job_id} nije pronađen.")
    _save_jobs(resolved_config, filtered)
    return {
        "status": "ok",
        "summary": f"Job {job_id} je uklonjen.",
        "jobId": job_id,
    }


def run_job_now(job_id: str, config: ControlCenterConfig | None = None) -> dict[str, object]:
    resolved_config = config or get_config()
    jobs = _load_jobs(resolved_config)
    target = next((job for job in jobs if job.get("id") == job_id), None)
    if not target:
        return action_result("error", "run-job-now", f"Job {job_id} nije pronađen.")
    executed = _execute_job(target, resolved_config)
    _save_jobs(resolved_config, jobs)
    return {
        "status": "ok" if executed.get("lastStatus") == "ok" else "error",
        "summary": str(executed.get("lastSummary", "")),
        "job": executed,
    }


def run_due_jobs(config: ControlCenterConfig | None = None) -> dict[str, object]:
    resolved_config = config or get_config()
    jobs = _load_jobs(resolved_config)
    now = _now_datetime()
    run_count = 0
    for job in jobs:
        if not job.get("enabled", True):
            continue
        run_at = _parse_iso(str(job.get("nextRunAt", "")))
        if run_at and run_at > now:
            continue
        _execute_job(job, resolved_config)
        run_count += 1
    _save_jobs(resolved_config, jobs)
    return {
        "status": "ok",
        "summary": f"Provereno je {len(jobs)} job-ova, pokrenuto {run_count}.",
        "checkedCount": len(jobs),
        "runCount": run_count,
        "jobs": jobs,
    }


def start_jobs_scheduler() -> None:
    global _SCHEDULER_THREAD
    with _SCHEDULER_LOCK:
        if _SCHEDULER_THREAD and _SCHEDULER_THREAD.is_alive():
            return
        _SCHEDULER_STOP.clear()
        _SCHEDULER_THREAD = threading.Thread(
            target=_scheduler_loop,
            name="lacc-jobs-scheduler",
            daemon=True,
        )
        _SCHEDULER_THREAD.start()


def stop_jobs_scheduler() -> None:
    _SCHEDULER_STOP.set()


def _scheduler_loop() -> None:
    while not _SCHEDULER_STOP.wait(SCHEDULER_POLL_SECONDS):
        try:
            run_due_jobs()
        except Exception:  # noqa: BLE001 - scheduler must stay alive even if one tick fails
            time.sleep(1.0)


def _load_jobs(config: ControlCenterConfig) -> list[dict[str, object]]:
    payload = read_json_object(config.jobs_registry_path)
    jobs = payload.get("jobs", [])
    if not isinstance(jobs, list):
        return []
    return [job for job in jobs if isinstance(job, dict)]


def _save_jobs(config: ControlCenterConfig, jobs: list[dict[str, object]]) -> None:
    atomic_write_json(config.jobs_registry_path, {"jobs": jobs})


def _normalize_job_payload(
    payload: dict[str, object],
    *,
    existing: dict[str, object] | None,
) -> dict[str, object]:
    job_id = str(payload.get("id") or (existing or {}).get("id") or _build_job_id(payload.get("name"))).strip()
    name = str(payload.get("name") or (existing or {}).get("name") or "Job").strip() or "Job"
    kind = str(payload.get("kind") or (existing or {}).get("kind") or "health-check").strip()
    if kind not in ALLOWED_JOB_KINDS:
        kind = "health-check"
    interval_minutes = _normalize_interval_minutes(payload.get("intervalMinutes"))
    enabled = bool(payload.get("enabled", True))
    target_id = str(payload.get("targetId") or (existing or {}).get("targetId") or "").strip()
    workflow_preset_id = str(payload.get("workflowPresetId") or (existing or {}).get("workflowPresetId") or "").strip()
    now = _now_datetime()
    next_run_at = now + timedelta(minutes=interval_minutes)
    return {
        "id": job_id,
        "name": name,
        "kind": kind,
        "intervalMinutes": interval_minutes,
        "enabled": enabled,
        "targetId": target_id,
        "workflowPresetId": workflow_preset_id,
        "createdAt": str((existing or {}).get("createdAt") or _now_iso()),
        "updatedAt": _now_iso(),
        "nextRunAt": next_run_at.isoformat(),
        "lastRunAt": str((existing or {}).get("lastRunAt") or ""),
        "lastStatus": str((existing or {}).get("lastStatus") or "idle"),
        "lastSummary": str((existing or {}).get("lastSummary") or "Job još nije pokretan."),
        "lastDetails": (existing or {}).get("lastDetails", {}),
    }


def _execute_job(job: dict[str, object], config: ControlCenterConfig) -> dict[str, object]:
    kind = str(job.get("kind", "health-check"))
    runner = _JOB_RUNNERS.get(kind, _run_health_check_job)
    try:
        result = runner(job)
        status = str(result.get("status", "ok"))
        summary = str(result.get("summary", "Job je završen."))
        details = result.get("details", {})
    except Exception as exc:  # noqa: BLE001
        status = "error"
        summary = f"Job {job.get('name', job.get('id', 'job'))} nije uspeo: {exc}"
        details = {"error": str(exc)}
    job["lastRunAt"] = _now_iso()
    job["lastStatus"] = status
    job["lastSummary"] = summary
    job["lastDetails"] = details if isinstance(details, dict) else {"details": details}
    job["updatedAt"] = _now_iso()
    job["nextRunAt"] = (_now_datetime() + timedelta(minutes=_normalize_interval_minutes(job.get("intervalMinutes")))).isoformat()
    _append_observability_snapshot(config, job)
    return job


def _append_observability_snapshot(config: ControlCenterConfig, job: dict[str, object]) -> None:
    payload = read_json_object(config.observability_snapshots_path)
    snapshots = payload.get("items", [])
    if not isinstance(snapshots, list):
        snapshots = []
    snapshots.insert(
        0,
        {
            "jobId": job.get("id", ""),
            "jobName": job.get("name", ""),
            "kind": job.get("kind", ""),
            "ranAt": job.get("lastRunAt", ""),
            "status": job.get("lastStatus", ""),
            "summary": job.get("lastSummary", ""),
        },
    )
    atomic_write_json(config.observability_snapshots_path, {"items": snapshots[:100]})


def _run_health_check_job(job: dict[str, object]) -> dict[str, object]:
    status = load_status_payload()
    observability = load_observability_payload()
    return {
        "status": "ok",
        "summary": f"Health snapshot: {status.get('runtimeLiveStatus', '--')} | {status.get('activeRuntimeLabel', '--')}",
        "details": {
            "runtime": status.get("activeRuntimeLabel", ""),
            "model": status.get("activeModel", ""),
            "telemetryFlow": observability.get("telemetry", {}).get("flowStateLabel", ""),
        },
    }


def _run_update_check_job(job: dict[str, object]) -> dict[str, object]:
    result = check_for_updates()
    return {
        "status": str(result.get("status", "ok")),
        "summary": str(result.get("summary", "Update check je završen.")),
        "details": result.get("details", {}),
    }


def _run_fleet_refresh_job(job: dict[str, object]) -> dict[str, object]:
    result = refresh_fleet_machine()
    return {
        "status": str(result.get("status", "ok")),
        "summary": str(result.get("summary", "Fleet refresh je završen.")),
        "details": {
            "machineCount": len(result.get("machines", [])) if isinstance(result.get("machines"), list) else 0,
        },
    }


def _run_benchmark_battery_job(job: dict[str, object]) -> dict[str, object]:
    target_id = str(job.get("targetId", "")).strip()
    if not target_id:
        benchmark_payload = load_benchmark_summary()
        selected = benchmark_payload.get("selectedBattery", {})
        if isinstance(selected, dict):
            target_id = str(selected.get("id", "")).strip()
    result = start_battery_benchmark(target_id)
    return {
        "status": str(result.get("status", "ok")),
        "summary": str(result.get("summary", "Benchmark battery job je završen.")),
        "details": result.get("details", {}),
    }


def _run_workflow_pulse_job(job: dict[str, object]) -> dict[str, object]:
    presets = load_workflow_presets()
    selected_id = str(job.get("workflowPresetId", "")).strip()
    selected = next((preset for preset in presets if preset.get("id") == selected_id), None)
    if selected is None:
        selected = presets[0] if presets else {"label": "Research", "summary": "Podrazumevani workflow."}
    fleet = load_fleet_summary()
    return {
        "status": "ok",
        "summary": f"Workflow pulse: {selected.get('label', 'Preset')} | fleet mašina {fleet.get('machineCount', 0)}",
        "details": {
            "presetId": selected.get("id", ""),
            "presetLabel": selected.get("label", ""),
            "presetSummary": selected.get("summary", ""),
            "machineCount": fleet.get("machineCount", 0),
        },
    }


_JOB_RUNNERS: dict[str, Callable[[dict[str, object]], dict[str, object]]] = {
    "health-check": _run_health_check_job,
    "update-check": _run_update_check_job,
    "fleet-refresh": _run_fleet_refresh_job,
    "benchmark-battery": _run_benchmark_battery_job,
    "workflow-pulse": _run_workflow_pulse_job,
}


def _normalize_interval_minutes(value: object) -> int:
    if isinstance(value, bool):
        value = DEFAULT_INTERVAL_MINUTES
    try:
        parsed = int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        parsed = DEFAULT_INTERVAL_MINUTES
    return max(MIN_INTERVAL_MINUTES, min(MAX_INTERVAL_MINUTES, parsed))


def _build_job_id(name: object) -> str:
    return f"job-{slugify_token(str(name or ''), fallback='job')}-{uuid4().hex[:8]}"


def _now_iso() -> str:
    return _now_datetime().isoformat()


def _now_datetime() -> datetime:
    return datetime.now(UTC)


def _parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
