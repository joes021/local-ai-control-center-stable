from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from uuid import uuid4

from local_ai_control_center_installer.control_center_backend.config import (
    ControlCenterConfig,
    get_config,
)
from local_ai_control_center_installer.control_center_backend.services.opencode_service import (
    _resolve_opencode_executable_path,
)
from local_ai_control_center_installer.control_center_backend.services.server_service import (
    _resolve_spec_type_for_runtime,
)
from local_ai_control_center_installer.control_center_backend.services.settings_service import (
    THINKING_PRESETS,
    apply_settings,
    load_effective_settings_state,
)
from local_ai_control_center_installer.control_center_backend.services.state_helpers import (
    action_result,
    atomic_write_json,
    read_json_list,
    read_json_object,
)
from local_ai_control_center_installer.control_center_backend.services.status_service import (
    classify_runtime_model_support,
    load_runtime_state,
)
from local_ai_control_center_installer.server_verification import (
    ServerVerificationTarget,
    _build_server_command,
)


TUNING_LAB_HISTORY_PAGE_SIZE = 10
TUNING_LAB_HISTORY_MAX_ITEMS = 100
TUNING_LAB_RUNTIME_PROFILE_MAX_ITEMS = 200
TUNING_LAB_SUCCESS_CHECK_LIMIT = 3
TUNING_LAB_DEFAULT_TIMEOUT_SECONDS = 30 * 60
TUNING_LAB_RUNTIME_READY_TIMEOUT_SECONDS = 180.0
TUNING_LAB_RUNTIME_READY_POLL_SECONDS = 0.5
TUNING_LAB_WORKER_POLL_SECONDS = 0.25
TUNING_LAB_DIFF_FILE_LIMIT = 10
TUNING_LAB_DIFF_FILE_BYTES_LIMIT = 200_000
TUNING_LAB_DIFF_LINES_LIMIT = 400

_RUN_LOCK = threading.Lock()
_RUNNER_THREAD: threading.Thread | None = None

_GOAL_OPTIONS = [
    {"id": "code", "label": "Kodiranje"},
    {"id": "chat", "label": "Chat"},
    {"id": "benchmark", "label": "Benchmark"},
    {"id": "low-vram", "label": "Low VRAM"},
    {"id": "long-context", "label": "Dug kontekst"},
]
_ALLOWED_GOAL_IDS = {item["id"] for item in _GOAL_OPTIONS}

_SUCCESS_CHECK_TEMPLATES = [
    {"id": "auto-detect", "label": "Auto-detect", "command": ""},
    {"id": "none", "label": "Bez provere", "command": ""},
    {"id": "pytest", "label": "Python / pytest", "command": "python -m pytest -q"},
    {"id": "npm-test", "label": "Node / npm test", "command": "npm test"},
    {"id": "cargo-test", "label": "Rust / cargo test", "command": "cargo test"},
]

_TUNING_SETTINGS_KEYS = (
    "profile",
    "context",
    "outputTokens",
    "thinkingMode",
    "temperature",
    "topK",
    "topP",
    "minP",
    "repeatPenalty",
    "repeatLastN",
    "presencePenalty",
    "frequencyPenalty",
    "seed",
)
_RUNTIME_PROFILE_ALLOWED_KEYS = set(_TUNING_SETTINGS_KEYS)
_DEFAULT_MODEL_FAMILY = "generic"

_GOAL_DEFAULTS: dict[str, dict[str, object]] = {
    "code": {
        "profile": "speed",
        "context": 131072,
        "outputTokens": 4096,
        "thinkingMode": "low",
        "temperature": 0.2,
        "topK": 20,
        "topP": 0.9,
        "minP": 0.0,
        "repeatPenalty": 1.03,
        "repeatLastN": 64,
        "presencePenalty": 0.0,
        "frequencyPenalty": 0.0,
        "seed": 7,
    },
    "chat": {
        "profile": "balanced",
        "context": 131072,
        "outputTokens": 8192,
        "thinkingMode": "mid",
        "temperature": 0.7,
        "topK": 40,
        "topP": 0.95,
        "minP": 0.05,
        "repeatPenalty": 1.0,
        "repeatLastN": 64,
        "presencePenalty": 0.0,
        "frequencyPenalty": 0.0,
        "seed": -1,
    },
    "benchmark": {
        "profile": "speed",
        "context": 65536,
        "outputTokens": 2048,
        "thinkingMode": "no-thinking",
        "temperature": 0.0,
        "topK": 1,
        "topP": 1.0,
        "minP": 0.0,
        "repeatPenalty": 1.0,
        "repeatLastN": 64,
        "presencePenalty": 0.0,
        "frequencyPenalty": 0.0,
        "seed": 7,
    },
    "low-vram": {
        "profile": "speed",
        "context": 65536,
        "outputTokens": 2048,
        "thinkingMode": "low",
        "temperature": 0.6,
        "topK": 20,
        "topP": 0.9,
        "minP": 0.0,
        "repeatPenalty": 1.05,
        "repeatLastN": 64,
        "presencePenalty": 0.0,
        "frequencyPenalty": 0.0,
        "seed": -1,
    },
    "long-context": {
        "profile": "balanced",
        "context": 262144,
        "outputTokens": 8192,
        "thinkingMode": "mid",
        "temperature": 0.6,
        "topK": 20,
        "topP": 0.95,
        "minP": 0.0,
        "repeatPenalty": 1.05,
        "repeatLastN": 64,
        "presencePenalty": 0.0,
        "frequencyPenalty": 0.0,
        "seed": -1,
    },
}


def load_tuning_lab_summary(
    *,
    history_page: int = 1,
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    resolved_config = config or get_config()
    history_items = _load_history(resolved_config)
    page = max(int(history_page or 1), 1)
    total_items = len(history_items)
    total_pages = max((total_items + TUNING_LAB_HISTORY_PAGE_SIZE - 1) // TUNING_LAB_HISTORY_PAGE_SIZE, 1)
    start_index = (page - 1) * TUNING_LAB_HISTORY_PAGE_SIZE
    end_index = start_index + TUNING_LAB_HISTORY_PAGE_SIZE
    run_state = _load_run_state(resolved_config)
    effective_settings = load_effective_settings_state(resolved_config)
    runtime_state = load_runtime_state(resolved_config)
    goal = str(run_state.get("activeRun", {}).get("goal", "code") if isinstance(run_state.get("activeRun"), dict) else "code")
    recommended_slot, recommended_origin = _build_recommended_slot(
        goal=goal,
        runtime_state=runtime_state,
        history_items=history_items,
        effective_settings=effective_settings,
    )
    return {
        "status": "ok",
        "activeRun": run_state["activeRun"],
        "queue": run_state["queue"],
        "history": history_items[start_index:end_index],
        "historyPage": page,
        "historyPageSize": TUNING_LAB_HISTORY_PAGE_SIZE,
        "historyTotalItems": total_items,
        "historyTotalPages": total_pages,
        "goalOptions": list(_GOAL_OPTIONS),
        "successCheckTemplates": list(_SUCCESS_CHECK_TEMPLATES),
        "slots": [
            _build_slot_from_settings(
                slot_id="baseline",
                label="Baseline",
                source="current-system",
                settings=_project_tuning_settings(effective_settings),
            ),
            recommended_slot,
            _build_slot_from_settings(
                slot_id="custom",
                label="Custom",
                source="manual",
                settings=_project_tuning_settings(effective_settings),
            ),
        ],
        "context": {
            "activeModel": str(runtime_state.get("active_model", "") or ""),
            "activeModelId": str(runtime_state.get("active_model_id", "") or ""),
            "activeRuntime": str(runtime_state.get("active_runtime", "") or ""),
            "workingDirectory": str(effective_settings.get("workingDirectory", resolved_config.install_root)),
            "modelFamily": _detect_model_family(
                str(runtime_state.get("active_model_id", "") or ""),
                str(runtime_state.get("active_model", "") or ""),
            ),
            "recommendedOrigin": recommended_origin,
        },
    }


def load_tuning_lab_run_status(
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    resolved_config = config or get_config()
    run_state = _load_run_state(resolved_config)
    active_run = run_state.get("activeRun")
    return dict(active_run) if isinstance(active_run, dict) else {}


def load_tuning_lab_history_page(
    *,
    page: int = 1,
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    return load_tuning_lab_summary(history_page=page, config=config)


def prepare_tuning_workspace(
    *,
    working_directory: str,
    experiment_id: str,
    slot_id: str,
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    resolved_config = config or get_config()
    source_dir = Path(str(working_directory or resolved_config.install_root)).expanduser().resolve()
    slot_root = _tuning_runs_root(resolved_config) / str(experiment_id or "run") / str(slot_id or "slot")
    slot_root.mkdir(parents=True, exist_ok=True)

    repo_root = _git_repo_root(source_dir)
    if repo_root is not None and _git_repo_is_clean(repo_root):
        worktree_root = slot_root / "worktree"
        if worktree_root.exists():
            shutil.rmtree(worktree_root, ignore_errors=True)
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree_root), "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        relative_subdir = source_dir.relative_to(repo_root) if source_dir != repo_root else Path(".")
        effective_workspace = worktree_root / relative_subdir if str(relative_subdir) != "." else worktree_root
        return {
            "mode": "git-worktree",
            "workspacePath": str(effective_workspace),
            "workspaceRoot": str(worktree_root),
            "cleanupPath": str(worktree_root),
            "sourceRoot": str(repo_root),
        }

    copy_root = slot_root / "copy"
    if copy_root.exists():
        shutil.rmtree(copy_root, ignore_errors=True)
    shutil.copytree(
        source_dir,
        copy_root,
        dirs_exist_ok=False,
        ignore=shutil.ignore_patterns(".git", ".pytest_cache", "__pycache__"),
    )
    return {
        "mode": "copy",
        "workspacePath": str(copy_root),
        "workspaceRoot": str(copy_root),
        "cleanupPath": str(copy_root),
        "sourceRoot": str(source_dir),
    }


def suggest_tuning_winner(slot_results: list[dict[str, Any]]) -> str | None:
    successful_slots = [
        slot
        for slot in slot_results
        if bool(slot.get("taskCompleted")) and bool(slot.get("successChecksPassed"))
    ]
    if not successful_slots:
        return None
    ranked = sorted(
        successful_slots,
        key=lambda slot: (
            float(slot.get("totalDurationMs", float("inf")) or float("inf")),
            -float(slot.get("averageOutputTokensPerSecond", 0.0) or 0.0),
            -float(slot.get("averageTotalTokensPerSecond", 0.0) or 0.0),
        ),
    )
    return str(ranked[0].get("id", "") or "") or None


def enqueue_tuning_experiment(
    payload: dict[str, Any],
    *,
    config: ControlCenterConfig | None = None,
    start_worker: bool = True,
) -> dict[str, Any]:
    resolved_config = config or get_config()
    experiment = _normalize_experiment_payload(payload, resolved_config)
    with _RUN_LOCK:
        run_state = _load_run_state(resolved_config)
        queue = list(run_state["queue"])
        queue.append(experiment)
        _save_run_state(resolved_config, active_run=run_state["activeRun"], queue=queue)
    if start_worker:
        _ensure_tuning_worker(resolved_config)
    return {
        "status": "accepted",
        "summary": f"Eksperiment {experiment['name']} je dodat u Tuning Lab red čekanja.",
        "runId": experiment["runId"],
    }


def run_next_tuning_experiment(
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    resolved_config = config or get_config()
    with _RUN_LOCK:
        run_state = _load_run_state(resolved_config)
        active_run = run_state["activeRun"]
        queue = list(run_state["queue"])
        if not active_run:
            if not queue:
                return {"status": "idle", "summary": "Tuning Lab red čekanja je prazan."}
            active_run = dict(queue.pop(0))
            active_run["status"] = "queued"
            active_run["queuedAt"] = str(active_run.get("queuedAt", "") or _now_iso())
            _save_run_state(resolved_config, active_run=active_run, queue=queue)

    completed = _execute_tuning_experiment(active_run, resolved_config)

    with _RUN_LOCK:
        history = _load_history(resolved_config)
        history.insert(0, completed)
        _save_history(resolved_config, history)
        run_state = _load_run_state(resolved_config)
        _save_run_state(resolved_config, active_run=None, queue=run_state["queue"])

    return {
        "status": "ok",
        "summary": str(completed.get("winnerSummary", "") or completed.get("summary", "Tuning Lab run je završen.")),
        "runId": str(completed.get("runId", "") or ""),
    }


def apply_tuning_lab_winner(
    run_id: str,
    *,
    slot_id: str | None = None,
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    resolved_config = config or get_config()
    experiment = _find_history_run(run_id, resolved_config)
    if experiment is None:
        return action_result("error", "apply-tuning-lab-winner", f"Run {run_id} nije pronađen.")
    selected_slot_id = str(slot_id or experiment.get("suggestedWinnerSlotId", "") or "").strip()
    if not selected_slot_id:
        return action_result("error", "apply-tuning-lab-winner", "Eksperiment nema predloženog pobednika.")
    selected_slot = next(
        (slot for slot in experiment.get("slots", []) if str(slot.get("id", "") or "") == selected_slot_id),
        None,
    )
    if not isinstance(selected_slot, dict):
        return action_result("error", "apply-tuning-lab-winner", f"Slot {selected_slot_id} nije pronađen.")
    settings_patch = selected_slot.get("settingsPatch")
    if not isinstance(settings_patch, dict):
        return action_result("error", "apply-tuning-lab-winner", "Izabrani slot nema settings patch.")
    current_settings = load_effective_settings_state(resolved_config)
    merged_payload = dict(current_settings)
    merged_payload.update(settings_patch)
    result = apply_settings(merged_payload, resolved_config)
    if result.get("status") == "ok":
        result["summary"] = f"Primenjen je pobednički set {selected_slot.get('label', selected_slot_id)} iz run-a {run_id}."
    return result


def export_tuning_lab_run(
    run_id: str,
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    resolved_config = config or get_config()
    experiment = _find_history_run(run_id, resolved_config)
    if experiment is None:
        return action_result("error", "export-tuning-lab-run", f"Run {run_id} nije pronađen.")
    return {
        "status": "ok",
        "summary": f"Eksperiment {run_id} je spreman za export/share.",
        "experiment": experiment,
    }


def import_tuning_snippet(
    snippet: str,
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    del config
    parsed = _parse_tuning_snippet(snippet)
    if not parsed:
        return action_result(
            "error",
            "import-tuning-snippet",
            "Snippet nije sadržao prepoznatljive inference parametre.",
        )
    return {
        "status": "ok",
        "summary": f"Prepoznato je {len(parsed)} inference vrednosti iz nalepljenog snippeta.",
        "settingsPatch": parsed,
    }


def create_tuning_runtime_profile(
    *,
    experiment_id: str,
    slot_id: str,
    settings_patch: dict[str, Any],
    upstream_base_url: str = "",
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    resolved_config = config or get_config()
    payload = read_json_object(resolved_config.tuning_lab_runtime_profiles_path)
    profiles = payload.get("profiles", [])
    if not isinstance(profiles, list):
        profiles = []
    normalized_patch = {
        key: settings_patch[key]
        for key in _RUNTIME_PROFILE_ALLOWED_KEYS
        if key in settings_patch
    }
    profile = {
        "token": uuid4().hex,
        "experimentId": str(experiment_id or "").strip(),
        "slotId": str(slot_id or "").strip(),
        "createdAt": _now_iso(),
        "upstreamBaseUrl": str(upstream_base_url or "").strip(),
        "settingsPatch": normalized_patch,
    }
    profiles.insert(0, profile)
    atomic_write_json(
        resolved_config.tuning_lab_runtime_profiles_path,
        {"profiles": profiles[:TUNING_LAB_RUNTIME_PROFILE_MAX_ITEMS]},
    )
    return dict(profile)


def resolve_tuning_runtime_profile(
    profile_token: str,
    config: ControlCenterConfig | None = None,
) -> dict[str, Any] | None:
    resolved_config = config or get_config()
    payload = read_json_object(resolved_config.tuning_lab_runtime_profiles_path)
    profiles = payload.get("profiles", [])
    if not isinstance(profiles, list):
        return None
    normalized_token = str(profile_token or "").strip()
    if not normalized_token:
        return None
    for item in profiles:
        if not isinstance(item, dict):
            continue
        if str(item.get("token", "") or "").strip() != normalized_token:
            continue
        settings_patch = item.get("settingsPatch")
        return {
            "token": normalized_token,
            "experimentId": str(item.get("experimentId", "") or "").strip(),
            "slotId": str(item.get("slotId", "") or "").strip(),
            "createdAt": str(item.get("createdAt", "") or ""),
            "upstreamBaseUrl": str(item.get("upstreamBaseUrl", "") or "").strip(),
            "settingsPatch": dict(settings_patch) if isinstance(settings_patch, dict) else {},
        }
    return None


def _execute_tuning_experiment(
    experiment: dict[str, Any],
    config: ControlCenterConfig,
) -> dict[str, Any]:
    active_run = deepcopy(experiment)
    active_run["status"] = "running"
    active_run["startedAt"] = _now_iso()
    active_run["currentIndex"] = 0
    active_run["currentSlotId"] = ""
    active_run["currentSlotLabel"] = ""
    slots = [dict(slot) for slot in active_run.get("slots", []) if isinstance(slot, dict)]
    active_run["slots"] = slots
    _write_active_run(config, active_run)

    runtime_state = load_runtime_state(config)
    active_run["activeRuntime"] = str(runtime_state.get("active_runtime", "") or "")
    active_run["modelId"] = str(runtime_state.get("active_model_id", "") or "")
    active_run["modelLabel"] = str(runtime_state.get("active_model", "") or "")
    active_run["modelFamily"] = _detect_model_family(
        active_run["modelId"],
        active_run["modelLabel"],
    )

    slot_results: list[dict[str, Any]] = []
    for index, slot in enumerate(slots, start=1):
        active_run["currentIndex"] = index
        active_run["currentSlotId"] = str(slot.get("id", "") or "")
        active_run["currentSlotLabel"] = str(slot.get("label", "") or "")
        for candidate in slots:
            candidate_id = str(candidate.get("id", "") or "")
            if candidate_id == active_run["currentSlotId"]:
                candidate["status"] = "running"
                candidate["summary"] = "Slot se trenutno izvršava."
            elif not candidate.get("status"):
                candidate["status"] = "queued"
                candidate["summary"] = "Slot čeka svoj red."
        _write_active_run(config, active_run)
        slot_result = _run_tuning_slot(active_run, slot, config)
        slot_results.append(slot_result)
        for candidate in slots:
            if str(candidate.get("id", "") or "") == str(slot_result.get("id", "") or ""):
                candidate.update(slot_result)
        _write_active_run(config, active_run)

    active_run["slots"] = slot_results
    active_run["currentIndex"] = len(slot_results)
    active_run["finishedAt"] = _now_iso()
    active_run["suggestedWinnerSlotId"] = suggest_tuning_winner(slot_results)
    active_run["winnerSummary"] = _build_winner_summary(active_run["suggestedWinnerSlotId"], slot_results)
    active_run["status"] = "completed" if active_run["suggestedWinnerSlotId"] else "failed"
    active_run["summary"] = active_run["winnerSummary"] or "Nijedan slot nije završio uspešno."
    active_run["currentSlotId"] = ""
    active_run["currentSlotLabel"] = ""
    _write_active_run(config, active_run)
    return active_run


def _run_tuning_slot(
    experiment: dict[str, Any],
    slot: dict[str, Any],
    config: ControlCenterConfig,
) -> dict[str, Any]:
    slot_id = str(slot.get("id", "") or "")
    slot_label = str(slot.get("label", slot_id) or slot_id)
    working_directory = str(experiment.get("workingDirectory", config.install_root) or config.install_root)
    workspace_info = prepare_tuning_workspace(
        working_directory=working_directory,
        experiment_id=str(experiment.get("runId", "") or "run"),
        slot_id=slot_id,
        config=config,
    )
    workspace_path = Path(str(workspace_info["workspacePath"]))
    cleanup_path = Path(str(workspace_info["cleanupPath"]))
    slot_artifact_root = _tuning_runs_root(config) / str(experiment.get("runId", "") or "run") / slot_id
    slot_artifact_root.mkdir(parents=True, exist_ok=True)
    before_snapshot = _snapshot_directory(workspace_path)
    merged_settings = _merge_slot_settings(slot.get("settingsPatch"), config)
    runtime_session: dict[str, Any] | None = None
    runtime_profile: dict[str, Any] | None = None
    opencode_result: dict[str, Any] | None = None
    success_checks: list[dict[str, Any]] = []
    started_at = _now_iso()
    started_monotonic = time.monotonic()
    error_summary = ""
    try:
        runtime_session = _launch_slot_runtime(
            slot_settings=merged_settings,
            slot_artifact_root=slot_artifact_root,
            config=config,
        )
        runtime_profile = create_tuning_runtime_profile(
            experiment_id=str(experiment.get("runId", "") or ""),
            slot_id=slot_id,
            settings_patch=merged_settings,
            upstream_base_url=str(runtime_session.get("baseUrl", "") or ""),
            config=config,
        )
        opencode_result = _run_slot_opencode_task(
            experiment=experiment,
            slot_settings=merged_settings,
            runtime_profile_token=str(runtime_profile.get("token", "") or ""),
            workspace_path=workspace_path,
            slot_artifact_root=slot_artifact_root,
            config=config,
        )
        success_check_specs = _resolve_success_check_specs(
            experiment=experiment,
            workspace_path=workspace_path,
        )
        success_checks = _run_success_checks(success_check_specs, workspace_path, slot_artifact_root)
    except Exception as exc:  # noqa: BLE001
        error_summary = str(exc)
        opencode_result = {
            "processReturncode": 1,
            "assistantText": "",
            "inputTokens": 0,
            "outputTokens": 0,
            "totalTokens": 0,
            "costUsd": 0.0,
            "stdoutPath": "",
            "stdoutText": "",
            "stderrText": error_summary,
            "averageOutputTokensPerSecond": 0.0,
            "averageTotalTokensPerSecond": 0.0,
        }
    finally:
        if runtime_session is not None:
            _stop_slot_runtime(runtime_session)

    after_snapshot = _snapshot_directory(workspace_path) if workspace_path.exists() else {}
    diff_artifacts = _build_diff_artifacts(before_snapshot, after_snapshot, workspace_path)
    process_returncode = (
        int(opencode_result.get("processReturncode", 1))
        if isinstance(opencode_result, dict)
        else 1
    )
    task_completed = bool(opencode_result) and process_returncode == 0
    success_checks_passed = all(bool(check.get("passed")) for check in success_checks) if success_checks else True
    total_duration_ms = int((time.monotonic() - started_monotonic) * 1000)
    finished_at = _now_iso()
    status = "completed" if task_completed and success_checks_passed else "failed"
    summary = (
        f"{slot_label} je završio zadatak i prošao success check."
        if status == "completed"
        else (
            error_summary
            or "Slot nije završio zadatak ili nije prošao success check."
        )
    )
    result = {
        "id": slot_id,
        "label": slot_label,
        "source": str(slot.get("source", "") or ""),
        "status": status,
        "summary": summary,
        "settingsPatch": merged_settings,
        "workspaceMode": str(workspace_info.get("mode", "") or ""),
        "workspacePath": str(workspace_path),
        "workspaceRetained": False,
        "startedAt": started_at,
        "finishedAt": finished_at,
        "taskCompleted": task_completed,
        "successChecksPassed": success_checks_passed,
        "successChecks": success_checks,
        "changedFiles": diff_artifacts["changedFiles"],
        "diffSummary": diff_artifacts["summary"],
        "diffText": diff_artifacts["diffText"],
        "assistantText": str(opencode_result.get("assistantText", "") if isinstance(opencode_result, dict) else ""),
        "processReturncode": process_returncode,
        "inputTokens": int(opencode_result.get("inputTokens", 0) if isinstance(opencode_result, dict) else 0),
        "outputTokens": int(opencode_result.get("outputTokens", 0) if isinstance(opencode_result, dict) else 0),
        "totalTokens": int(opencode_result.get("totalTokens", 0) if isinstance(opencode_result, dict) else 0),
        "costUsd": float(opencode_result.get("costUsd", 0.0) if isinstance(opencode_result, dict) else 0.0),
        "totalDurationMs": total_duration_ms,
        "averageOutputTokensPerSecond": float(opencode_result.get("averageOutputTokensPerSecond", 0.0) if isinstance(opencode_result, dict) else 0.0),
        "averageTotalTokensPerSecond": float(opencode_result.get("averageTotalTokensPerSecond", 0.0) if isinstance(opencode_result, dict) else 0.0),
        "runtimeCommand": str(runtime_session.get("commandPreview", "") if isinstance(runtime_session, dict) else ""),
        "runtimeBaseUrl": str(runtime_session.get("baseUrl", "") if isinstance(runtime_session, dict) else ""),
        "opencodeCommand": str(opencode_result.get("commandPreview", "") if isinstance(opencode_result, dict) else ""),
        "stdoutPath": str(opencode_result.get("stdoutPath", "") if isinstance(opencode_result, dict) else ""),
    }
    _cleanup_workspace_path(workspace_info)
    return result


def _launch_slot_runtime(
    *,
    slot_settings: dict[str, Any],
    slot_artifact_root: Path,
    config: ControlCenterConfig,
) -> dict[str, Any]:
    runtime_state = load_runtime_state(config)
    runtime_name = str(runtime_state.get("active_runtime", "") or "")
    binary_path = Path(str(runtime_state.get("active_binary", "") or ""))
    if not binary_path.is_file():
        raise RuntimeError("Aktivni runtime binar nije pronađen za Tuning Lab.")
    model_id = str(runtime_state.get("active_model_id", "") or "")
    model_path = Path(str(runtime_state.get("active_model_path", "") or ""))
    if not model_path.is_file():
        raise RuntimeError("Aktivni model nije pronađen za Tuning Lab.")
    supported, support_reason = classify_runtime_model_support(
        model_id=model_id,
        model_path=model_path,
        runtime_name=runtime_name,
        runtime_binary_path=binary_path,
    )
    if not supported:
        raise RuntimeError(support_reason or "Aktivni model nije podržan za ovaj runtime.")

    port = _allocate_free_port()
    base_url = f"http://127.0.0.1:{port}"
    spec_type = _resolve_spec_type_for_runtime(runtime_state, binary_path, runtime_name)
    command = _build_server_command(
        ServerVerificationTarget(
            server_executable=binary_path,
            model_id=model_id,
            model_path=model_path,
            active_model_config_path=config.active_model_config_path,
        ),
        port,
        ctx_size=int(slot_settings.get("context", 262144) or 262144),
        spec_type=spec_type,
        temperature=float(slot_settings.get("temperature", 0.8)),
        top_k=int(slot_settings.get("topK", 40)),
        top_p=float(slot_settings.get("topP", 0.95)),
        min_p=float(slot_settings.get("minP", 0.05)),
        repeat_penalty=float(slot_settings.get("repeatPenalty", 1.0)),
        repeat_last_n=int(slot_settings.get("repeatLastN", 64)),
        presence_penalty=float(slot_settings.get("presencePenalty", 0.0)),
        frequency_penalty=float(slot_settings.get("frequencyPenalty", 0.0)),
        seed=int(slot_settings.get("seed", -1)),
    )
    log_path = slot_artifact_root / "runtime.log"
    process = _launch_background_process(command, log_path)
    if not _wait_for_runtime_ready(base_url, process, timeout_seconds=TUNING_LAB_RUNTIME_READY_TIMEOUT_SECONDS):
        _stop_process(process)
        log_excerpt = log_path.read_text(encoding="utf-8", errors="replace")[-4000:] if log_path.exists() else ""
        raise RuntimeError(
            "Tuning Lab runtime nije postao spreman. "
            + (f"Log: {log_excerpt}" if log_excerpt else "Health endpoint nije odgovorio na vreme.")
        )
    return {
        "process": process,
        "baseUrl": base_url,
        "commandPreview": subprocess.list2cmdline(command),
        "logPath": str(log_path),
    }


def _run_slot_opencode_task(
    *,
    experiment: dict[str, Any],
    slot_settings: dict[str, Any],
    runtime_profile_token: str,
    workspace_path: Path,
    slot_artifact_root: Path,
    config: ControlCenterConfig,
) -> dict[str, Any]:
    executable_path = _resolve_opencode_executable_path(config)
    if not executable_path.is_file():
        raise RuntimeError("OpenCode executable nije pronađen za Tuning Lab.")
    managed_config_path = config.opencode_managed_config_path
    if not managed_config_path.is_file():
        raise RuntimeError("OpenCode managed config nije pronađen za Tuning Lab.")

    runtime_state = load_runtime_state(config)
    public_model_name = Path(str(runtime_state.get("active_model_path", "") or "")).name
    if not public_model_name:
        public_model_name = str(runtime_state.get("active_model", "") or "").strip()
    if not public_model_name:
        raise RuntimeError("Aktivni model nije poznat za OpenCode Tuning Lab run.")

    base_url = f"http://127.0.0.1:{config.ui_port}/api/runtime-proxy/tuning/{runtime_profile_token}/v1"
    override_payload = {
        "autoupdate": False,
        "model": f"local-lacc/{public_model_name}",
        "enabled_providers": ["local-lacc"],
        "provider": {
            "local-lacc": {
                "npm": "@ai-sdk/openai-compatible",
                "options": {"baseURL": base_url},
                "models": {
                    public_model_name: {"name": public_model_name}
                },
            }
        },
    }
    env = _build_slot_opencode_env(
        managed_config_path=managed_config_path,
        slot_settings=slot_settings,
        override_payload=override_payload,
    )
    prompt = str(experiment.get("taskPrompt", "") or "").strip()
    if not prompt:
        raise RuntimeError("Tuning Lab eksperiment nema OpenCode task prompt.")
    command = [
        str(executable_path),
        "--pure",
        "run",
        "--format",
        "json",
        "--dir",
        str(workspace_path),
        "--dangerously-skip-permissions",
        "--model",
        f"local-lacc/{public_model_name}",
        prompt,
    ]
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=str(workspace_path),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TUNING_LAB_DEFAULT_TIMEOUT_SECONDS,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    total_duration_seconds = max(time.monotonic() - started, 0.001)
    stdout_text = str(completed.stdout or "")
    stderr_text = str(completed.stderr or "")
    stdout_path = slot_artifact_root / "opencode-output.jsonl"
    stdout_path.write_text(stdout_text, encoding="utf-8")
    parsed = _parse_opencode_json_output(stdout_text)
    output_tokens = int(parsed.get("outputTokens", 0))
    total_tokens = int(parsed.get("totalTokens", 0))
    return {
        "processReturncode": int(completed.returncode),
        "assistantText": str(parsed.get("assistantText", "") or ""),
        "inputTokens": int(parsed.get("inputTokens", 0)),
        "outputTokens": output_tokens,
        "totalTokens": total_tokens,
        "costUsd": float(parsed.get("costUsd", 0.0)),
        "stdoutPath": str(stdout_path),
        "stdoutText": stdout_text,
        "stderrText": stderr_text,
        "commandPreview": subprocess.list2cmdline(command),
        "averageOutputTokensPerSecond": (output_tokens / total_duration_seconds) if output_tokens > 0 else 0.0,
        "averageTotalTokensPerSecond": (total_tokens / total_duration_seconds) if total_tokens > 0 else 0.0,
    }


def _resolve_success_check_specs(
    *,
    experiment: dict[str, Any],
    workspace_path: Path,
) -> list[dict[str, str]]:
    raw_checks = experiment.get("successChecks")
    if isinstance(raw_checks, list) and raw_checks:
        checks: list[dict[str, str]] = []
        for item in raw_checks[:TUNING_LAB_SUCCESS_CHECK_LIMIT]:
            if not isinstance(item, dict):
                continue
            command = str(item.get("command", "") or "").strip()
            label = str(item.get("label", command or "Check") or "Check").strip()
            if not command:
                continue
            checks.append(
                {
                    "label": label,
                    "command": command,
                    "kind": str(item.get("kind", "custom") or "custom"),
                }
            )
        return checks
    return _auto_detect_success_checks(workspace_path)


def _run_success_checks(
    checks: list[dict[str, str]],
    workspace_path: Path,
    slot_artifact_root: Path,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, check_spec in enumerate(checks, start=1):
        command = str(check_spec.get("command", "") or "").strip()
        if not command:
            continue
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            cwd=str(workspace_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        log_path = slot_artifact_root / f"success-check-{index}.log"
        log_path.write_text(
            f"$ {command}\n\nSTDOUT\n{completed.stdout}\n\nSTDERR\n{completed.stderr}",
            encoding="utf-8",
        )
        result = {
            "label": str(check_spec.get("label", command) or command),
            "command": command,
            "kind": str(check_spec.get("kind", "custom") or "custom"),
            "returncode": int(completed.returncode),
            "passed": int(completed.returncode) == 0,
            "stdoutPath": str(log_path),
            "stdoutPreview": str(completed.stdout or "")[-1200:],
            "stderrPreview": str(completed.stderr or "")[-1200:],
        }
        results.append(result)
        if not result["passed"]:
            break
    return results


def _build_slot_from_settings(
    *,
    slot_id: str,
    label: str,
    source: str,
    settings: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": slot_id,
        "label": label,
        "source": source,
        "settingsPatch": settings,
        "status": "",
        "summary": "",
    }


def _build_recommended_slot(
    *,
    goal: str,
    runtime_state: dict[str, Any],
    history_items: list[dict[str, Any]],
    effective_settings: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    model_id = str(runtime_state.get("active_model_id", "") or "")
    model_label = str(runtime_state.get("active_model", "") or "")
    family = _detect_model_family(model_id, model_label)
    recommended_from_history = _find_history_recommendation(
        goal=goal,
        model_id=model_id,
        model_family=family,
        history_items=history_items,
    )
    if recommended_from_history is not None:
        return (
            _build_slot_from_settings(
                slot_id="recommended",
                label="Recommended",
                source="history",
                settings=recommended_from_history,
            ),
            "istorija modela/mašine",
        )
    defaults = dict(_GOAL_DEFAULTS.get(goal, _GOAL_DEFAULTS["code"]))
    merged = dict(_project_tuning_settings(effective_settings))
    merged.update(defaults)
    return (
        _build_slot_from_settings(
            slot_id="recommended",
            label="Recommended",
            source="rules",
            settings=merged,
        ),
        "interna pravila",
    )


def _find_history_recommendation(
    *,
    goal: str,
    model_id: str,
    model_family: str,
    history_items: list[dict[str, Any]],
) -> dict[str, Any] | None:
    def match(item: dict[str, Any], *, require_model: bool, require_family: bool) -> dict[str, Any] | None:
        if str(item.get("goal", "") or "") != goal:
            return None
        if require_model and str(item.get("modelId", "") or "") != model_id:
            return None
        if require_family and str(item.get("modelFamily", "") or "") != model_family:
            return None
        slot_id = str(item.get("suggestedWinnerSlotId", "") or "")
        if not slot_id:
            return None
        slots = item.get("slots")
        if not isinstance(slots, list):
            return None
        for slot in slots:
            if not isinstance(slot, dict):
                continue
            if str(slot.get("id", "") or "") != slot_id:
                continue
            patch = slot.get("settingsPatch")
            if isinstance(patch, dict):
                return _normalize_tuning_settings(patch)
        return None

    for item in history_items:
        if not isinstance(item, dict):
            continue
        candidate = match(item, require_model=True, require_family=False)
        if candidate is not None:
            return candidate
    for item in history_items:
        if not isinstance(item, dict):
            continue
        candidate = match(item, require_model=False, require_family=True)
        if candidate is not None:
            return candidate
    return None


def _normalize_experiment_payload(
    payload: dict[str, Any],
    config: ControlCenterConfig,
) -> dict[str, Any]:
    effective_settings = load_effective_settings_state(config)
    runtime_state = load_runtime_state(config)
    goal = str(payload.get("goal", "code") or "code").strip().lower()
    if goal not in _ALLOWED_GOAL_IDS:
        goal = "code"
    history_items = _load_history(config)
    recommended_slot, recommended_origin = _build_recommended_slot(
        goal=goal,
        runtime_state=runtime_state,
        history_items=history_items,
        effective_settings=effective_settings,
    )
    baseline_slot = _build_slot_from_settings(
        slot_id="baseline",
        label="Baseline",
        source="current-system",
        settings=_project_tuning_settings(effective_settings),
    )
    custom_slot = _build_slot_from_settings(
        slot_id="custom",
        label="Custom",
        source="manual",
        settings=_project_tuning_settings(effective_settings),
    )
    provided_slots = payload.get("slots")
    slot_map = {
        "baseline": baseline_slot,
        "recommended": recommended_slot,
        "custom": custom_slot,
    }
    if isinstance(provided_slots, list):
        for provided in provided_slots:
            if not isinstance(provided, dict):
                continue
            slot_id = str(provided.get("id", "") or "").strip().lower()
            if slot_id not in slot_map:
                continue
            existing = dict(slot_map[slot_id])
            if "label" in provided:
                existing["label"] = str(provided.get("label", existing["label"]) or existing["label"])
            if "source" in provided:
                existing["source"] = str(provided.get("source", existing["source"]) or existing["source"])
            existing_patch = dict(existing.get("settingsPatch", {}))
            if isinstance(provided.get("settingsPatch"), dict):
                existing_patch.update(_normalize_tuning_settings(provided["settingsPatch"]))
            existing["settingsPatch"] = existing_patch
            slot_map[slot_id] = existing

    name = str(payload.get("name", "") or "").strip() or f"Tuning Lab {goal}"
    working_directory = str(payload.get("workingDirectory", effective_settings.get("workingDirectory", config.install_root)) or config.install_root).strip()
    experiment = {
        "runId": f"tuning-{uuid4().hex[:10]}",
        "name": name,
        "goal": goal,
        "goalLabel": next((item["label"] for item in _GOAL_OPTIONS if item["id"] == goal), goal),
        "taskPrompt": str(payload.get("taskPrompt", "") or "").strip(),
        "workingDirectory": working_directory,
        "queuedAt": _now_iso(),
        "status": "queued",
        "recommendedOrigin": recommended_origin,
        "successChecks": _normalize_success_check_payload(payload.get("successChecks")),
        "slots": [slot_map["baseline"], slot_map["recommended"], slot_map["custom"]],
    }
    return experiment


def _normalize_success_check_payload(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in value[:TUNING_LAB_SUCCESS_CHECK_LIMIT]:
        if not isinstance(item, dict):
            continue
        command = str(item.get("command", "") or "").strip()
        if not command:
            continue
        normalized.append(
            {
                "label": str(item.get("label", command) or command).strip(),
                "command": command,
                "kind": str(item.get("kind", "custom") or "custom").strip() or "custom",
            }
        )
    return normalized


def _project_tuning_settings(settings: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_tuning_settings(settings)
    thinking_mode = str(normalized.get("thinkingMode", "mid") or "mid")
    preset = THINKING_PRESETS.get(thinking_mode, THINKING_PRESETS["mid"])
    normalized["buildSteps"] = int(preset["buildSteps"])
    normalized["planSteps"] = int(preset["planSteps"])
    normalized["generalSteps"] = int(preset["generalSteps"])
    normalized["exploreSteps"] = int(preset["exploreSteps"])
    return normalized


def _normalize_tuning_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    thinking_mode = str(raw.get("thinkingMode", "mid") or "mid").strip().lower()
    if thinking_mode not in THINKING_PRESETS:
        thinking_mode = "mid"
    profile = str(raw.get("profile", "balanced") or "balanced").strip().lower()
    if profile not in {"balanced", "speed", "video"}:
        profile = "balanced"
    return {
        "profile": profile,
        "context": _positive_int(raw.get("context"), 262144),
        "outputTokens": _positive_int(raw.get("outputTokens"), 8192),
        "thinkingMode": thinking_mode,
        "temperature": _bounded_float(raw.get("temperature"), 0.8, minimum=0.0, maximum=2.0),
        "topK": _non_negative_int(raw.get("topK"), 40),
        "topP": _bounded_float(raw.get("topP"), 0.95, minimum=0.0, maximum=1.0),
        "minP": _bounded_float(raw.get("minP"), 0.05, minimum=0.0, maximum=1.0),
        "repeatPenalty": _bounded_float(raw.get("repeatPenalty"), 1.0, minimum=0.0, maximum=2.5),
        "repeatLastN": _integer_value(raw.get("repeatLastN"), 64),
        "presencePenalty": _bounded_float(raw.get("presencePenalty"), 0.0, minimum=-2.0, maximum=2.0),
        "frequencyPenalty": _bounded_float(raw.get("frequencyPenalty"), 0.0, minimum=-2.0, maximum=2.0),
        "seed": _integer_value(raw.get("seed"), -1),
    }


def _merge_slot_settings(
    slot_settings: object,
    config: ControlCenterConfig,
) -> dict[str, Any]:
    merged = _project_tuning_settings(load_effective_settings_state(config))
    if isinstance(slot_settings, dict):
        merged.update(_normalize_tuning_settings(slot_settings))
    thinking_mode = str(merged.get("thinkingMode", "mid") or "mid")
    preset = THINKING_PRESETS.get(thinking_mode, THINKING_PRESETS["mid"])
    merged["buildSteps"] = int(preset["buildSteps"])
    merged["planSteps"] = int(preset["planSteps"])
    merged["generalSteps"] = int(preset["generalSteps"])
    merged["exploreSteps"] = int(preset["exploreSteps"])
    return merged


def _build_slot_opencode_env(
    *,
    managed_config_path: Path,
    slot_settings: dict[str, Any],
    override_payload: dict[str, Any],
) -> dict[str, str]:
    env = dict(os.environ)
    env["OPENCODE_CONFIG"] = str(managed_config_path)
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps(override_payload)
    env["OPENCODE_DISABLE_MODELS_FETCH"] = "true"
    env["LACC_PROFILE"] = str(slot_settings.get("profile", "balanced"))
    env["LACC_OPENCODE_SECURITY_MODE"] = "open"
    env["LACC_OPENCODE_CAPABILITY_MODE"] = "auto-commands"
    env["LACC_OPENCODE_BUILD_STEPS"] = str(slot_settings.get("buildSteps", 140))
    env["LACC_OPENCODE_PLAN_STEPS"] = str(slot_settings.get("planSteps", 100))
    env["LACC_OPENCODE_GENERAL_STEPS"] = str(slot_settings.get("generalSteps", 110))
    env["LACC_OPENCODE_EXPLORE_STEPS"] = str(slot_settings.get("exploreSteps", 80))
    return env


def _parse_opencode_json_output(output_text: str) -> dict[str, Any]:
    assistant_chunks: list[str] = []
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    cost_usd = 0.0
    for raw_line in output_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("type") == "text":
            text_value = str(payload.get("text", "") or "")
            if text_value:
                assistant_chunks.append(text_value)
        if payload.get("type") == "step_finish":
            tokens = payload.get("tokens", {})
            if isinstance(tokens, dict):
                input_tokens = int(tokens.get("input", input_tokens) or input_tokens)
                output_tokens = int(tokens.get("output", output_tokens) or output_tokens)
                total_tokens = int(tokens.get("total", total_tokens) or total_tokens)
            try:
                cost_usd = float(payload.get("cost", cost_usd) or cost_usd)
            except (TypeError, ValueError):
                pass
    if total_tokens <= 0:
        total_tokens = input_tokens + output_tokens
    return {
        "assistantText": "".join(assistant_chunks).strip(),
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "totalTokens": total_tokens,
        "costUsd": cost_usd,
    }


def _auto_detect_success_checks(workspace_path: Path) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    package_json_path = workspace_path / "package.json"
    if package_json_path.is_file():
        try:
            payload = json.loads(package_json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        scripts = payload.get("scripts", {}) if isinstance(payload, dict) else {}
        if isinstance(scripts, dict):
            if isinstance(scripts.get("lint"), str):
                checks.append({"label": "npm lint", "command": "npm run lint", "kind": "auto"})
            if isinstance(scripts.get("test"), str):
                checks.append({"label": "npm test", "command": "npm test", "kind": "auto"})
            if isinstance(scripts.get("build"), str):
                checks.append({"label": "npm build", "command": "npm run build", "kind": "auto"})
        if checks:
            return checks[:TUNING_LAB_SUCCESS_CHECK_LIMIT]

    if any((workspace_path / candidate).exists() for candidate in ("pytest.ini", "pyproject.toml", "tox.ini")):
        return [{"label": "pytest", "command": "python -m pytest -q", "kind": "auto"}]

    if (workspace_path / "Cargo.toml").is_file():
        return [{"label": "cargo test", "command": "cargo test", "kind": "auto"}]

    return []


def _build_diff_artifacts(
    before_snapshot: dict[str, str],
    after_snapshot: dict[str, str],
    workspace_path: Path,
) -> dict[str, Any]:
    changed_files = sorted(
        path
        for path in set(before_snapshot.keys()) | set(after_snapshot.keys())
        if before_snapshot.get(path) != after_snapshot.get(path)
    )
    summary = "Bez izmena" if not changed_files else f"{len(changed_files)} fajl(ova) je promenjeno."
    diff_blocks: list[str] = []
    for relative_path in changed_files[:TUNING_LAB_DIFF_FILE_LIMIT]:
        absolute_path = workspace_path / relative_path
        before_lines = _read_snapshot_text(before_snapshot, workspace_path, relative_path)
        after_lines = _read_snapshot_text(after_snapshot, workspace_path, relative_path)
        if before_lines is None or after_lines is None:
            diff_blocks.append(f"*** {relative_path}\n(binarni ili prevelik fajl)\n")
            continue
        diff_lines = list(
            difflib.unified_diff(
                before_lines,
                after_lines,
                fromfile=f"a/{relative_path}",
                tofile=f"b/{relative_path}",
                lineterm="",
            )
        )
        if diff_lines:
            diff_blocks.append("\n".join(diff_lines[:TUNING_LAB_DIFF_LINES_LIMIT]))
    return {
        "changedFiles": changed_files,
        "summary": summary,
        "diffText": "\n\n".join(diff_blocks).strip(),
    }


def _snapshot_directory(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    snapshot: dict[str, str] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.parts:
            continue
        try:
            relative = path.relative_to(root).as_posix()
            digest = hashlib.sha1(path.read_bytes()).hexdigest()  # noqa: S324 - non-security diff fingerprint
        except OSError:
            continue
        snapshot[relative] = digest
    return snapshot


def _read_snapshot_text(
    snapshot: dict[str, str],
    workspace_path: Path,
    relative_path: str,
) -> list[str] | None:
    if relative_path not in snapshot:
        return []
    absolute_path = workspace_path / relative_path
    try:
        size = absolute_path.stat().st_size
    except OSError:
        return None
    if size > TUNING_LAB_DIFF_FILE_BYTES_LIMIT:
        return None
    try:
        return absolute_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None


def _load_run_state(config: ControlCenterConfig) -> dict[str, Any]:
    payload = read_json_object(config.tuning_lab_run_state_path)
    active_run = payload.get("activeRun")
    queue = payload.get("queue")
    return {
        "activeRun": dict(active_run) if isinstance(active_run, dict) else None,
        "queue": [dict(item) for item in queue if isinstance(item, dict)] if isinstance(queue, list) else [],
    }


def _save_run_state(
    config: ControlCenterConfig,
    *,
    active_run: dict[str, Any] | None,
    queue: list[dict[str, Any]],
) -> None:
    atomic_write_json(
        config.tuning_lab_run_state_path,
        {
            "activeRun": active_run,
            "queue": queue,
        },
    )


def _write_active_run(config: ControlCenterConfig, active_run: dict[str, Any]) -> None:
    with _RUN_LOCK:
        current = _load_run_state(config)
        _save_run_state(config, active_run=active_run, queue=current["queue"])


def _load_history(config: ControlCenterConfig) -> list[dict[str, Any]]:
    return read_json_list(config.tuning_lab_history_path)


def _save_history(config: ControlCenterConfig, items: list[dict[str, Any]]) -> None:
    atomic_write_json(config.tuning_lab_history_path, items[:TUNING_LAB_HISTORY_MAX_ITEMS])


def _find_history_run(run_id: str, config: ControlCenterConfig) -> dict[str, Any] | None:
    normalized_run_id = str(run_id or "").strip()
    for item in _load_history(config):
        if str(item.get("runId", "") or "").strip() == normalized_run_id:
            return item
    return None


def _ensure_tuning_worker(config: ControlCenterConfig | None = None) -> None:
    del config
    global _RUNNER_THREAD
    with _RUN_LOCK:
        if _RUNNER_THREAD and _RUNNER_THREAD.is_alive():
            return
        _RUNNER_THREAD = threading.Thread(
            target=_tuning_worker_loop,
            name="lacc-tuning-lab-worker",
            daemon=True,
        )
        _RUNNER_THREAD.start()


def _tuning_worker_loop() -> None:
    while True:
        processed = run_next_tuning_experiment()
        if processed.get("status") == "idle":
            return
        time.sleep(TUNING_LAB_WORKER_POLL_SECONDS)


def _tuning_runs_root(config: ControlCenterConfig) -> Path:
    return config.control_center_config_root / "tuning-lab" / "runs"


def _git_repo_root(path: Path) -> Path | None:
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return None
    output = str(completed.stdout or "").strip()
    return Path(output).resolve() if output else None


def _git_repo_is_clean(repo_root: Path) -> bool:
    completed = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.returncode == 0 and not str(completed.stdout or "").strip()


def _cleanup_workspace_path(workspace_info: dict[str, Any]) -> None:
    cleanup_path = Path(str(workspace_info.get("cleanupPath", "") or ""))
    if not cleanup_path.exists():
        return
    mode = str(workspace_info.get("mode", "") or "")
    if mode == "git-worktree":
        repo_root_raw = str(workspace_info.get("sourceRoot", "") or "")
        repo_root = Path(repo_root_raw) if repo_root_raw else _git_repo_root(cleanup_path)
        if repo_root is not None:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(cleanup_path)],
                cwd=str(repo_root),
                check=False,
                capture_output=True,
                text=True,
            )
            return
    shutil.rmtree(cleanup_path, ignore_errors=True)


def _detect_model_family(model_id: str, model_label: str) -> str:
    joined = f"{model_id} {model_label}".lower()
    if "qwen" in joined:
        return "qwen"
    if "gemma" in joined:
        return "gemma"
    if "llama" in joined:
        return "llama"
    return _DEFAULT_MODEL_FAMILY


def _allocate_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _launch_background_process(command: list[str], log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("w", encoding="utf-8")
    try:
        process = subprocess.Popen(
            command,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        log_handle.close()
        raise
    setattr(process, "_lacc_log_handle", log_handle)
    return process


def _wait_for_runtime_ready(base_url: str, process, *, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + max(timeout_seconds, 0.0)
    while time.monotonic() <= deadline:
        if process.poll() is not None:
            return False
        try:
            with urlopen(f"{base_url}/health", timeout=1.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 503:
                time.sleep(TUNING_LAB_RUNTIME_READY_POLL_SECONDS)
                continue
            time.sleep(TUNING_LAB_RUNTIME_READY_POLL_SECONDS)
            continue
        except (URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
            time.sleep(TUNING_LAB_RUNTIME_READY_POLL_SECONDS)
            continue
        if isinstance(payload, dict) and payload.get("status") == "ok":
            return True
        time.sleep(TUNING_LAB_RUNTIME_READY_POLL_SECONDS)
    return False


def _stop_slot_runtime(runtime_session: dict[str, Any]) -> None:
    process = runtime_session.get("process")
    if process is None:
        return
    _stop_process(process)


def _stop_process(process) -> None:
    try:
        process.terminate()
    except OSError:
        return
    deadline = time.monotonic() + 10.0
    while time.monotonic() <= deadline:
        if process.poll() is not None:
            break
        time.sleep(0.1)
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass
    log_handle = getattr(process, "_lacc_log_handle", None)
    if log_handle is not None:
        try:
            log_handle.close()
        except OSError:
            pass


def _build_winner_summary(winner_slot_id: str | None, slot_results: list[dict[str, Any]]) -> str:
    if not winner_slot_id:
        return "Tuning Lab nije pronašao slot koji uspešno završava zadatak."
    winning_slot = next(
        (slot for slot in slot_results if str(slot.get("id", "") or "") == winner_slot_id),
        None,
    )
    if not isinstance(winning_slot, dict):
        return "Tuning Lab je predložio pobednika, ali detalji više nisu dostupni."
    return (
        f"{winning_slot.get('label', winner_slot_id)} je predložen kao pobednik "
        f"zato što je uspešno završio zadatak i bio najbrži među uspešnim slotovima."
    )


def _parse_tuning_snippet(snippet: str) -> dict[str, Any]:
    text = str(snippet or "").strip()
    if not text:
        return {}
    extracted: dict[str, Any] = {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        json_key_map = {
            "temperature": "temperature",
            "topK": "topK",
            "topP": "topP",
            "minP": "minP",
            "repeatPenalty": "repeatPenalty",
            "repeatLastN": "repeatLastN",
            "presencePenalty": "presencePenalty",
            "frequencyPenalty": "frequencyPenalty",
            "seed": "seed",
            "context": "context",
            "outputTokens": "outputTokens",
        }
        for source_key, target_key in json_key_map.items():
            if source_key in payload:
                extracted[target_key] = payload[source_key]
        if extracted:
            return _normalize_tuning_settings(extracted)

    pattern_specs = [
        (r"--temp\s+([0-9.\-]+)", "temperature", float),
        (r"--top-k\s+([0-9\-]+)", "topK", int),
        (r"--top-p\s+([0-9.\-]+)", "topP", float),
        (r"--min-p\s+([0-9.\-]+)", "minP", float),
        (r"--repeat-penalty\s+([0-9.\-]+)", "repeatPenalty", float),
        (r"--repeat-last-n\s+([0-9\-]+)", "repeatLastN", int),
        (r"--presence-penalty\s+([0-9.\-]+)", "presencePenalty", float),
        (r"--frequency-penalty\s+([0-9.\-]+)", "frequencyPenalty", float),
        (r"--seed\s+([0-9\-]+)", "seed", int),
        (r"--ctx-size\s+([0-9]+)", "context", int),
        (r"--n-predict\s+([0-9]+)", "outputTokens", int),
        (r"temperature\s*[:=]\s*([0-9.\-]+)", "temperature", float),
        (r"top[_ -]?k\s*[:=]\s*([0-9\-]+)", "topK", int),
        (r"top[_ -]?p\s*[:=]\s*([0-9.\-]+)", "topP", float),
        (r"min[_ -]?p\s*[:=]\s*([0-9.\-]+)", "minP", float),
        (r"repeat[_ -]?penalty\s*[:=]\s*([0-9.\-]+)", "repeatPenalty", float),
        (r"repeat[_ -]?last[_ -]?n\s*[:=]\s*([0-9\-]+)", "repeatLastN", int),
        (r"presence[_ -]?penalty\s*[:=]\s*([0-9.\-]+)", "presencePenalty", float),
        (r"frequency[_ -]?penalty\s*[:=]\s*([0-9.\-]+)", "frequencyPenalty", float),
        (r"seed\s*[:=]\s*([0-9\-]+)", "seed", int),
        (r"context\s*[:=]\s*([0-9]+)", "context", int),
        (r"output[_ -]?tokens\s*[:=]\s*([0-9]+)", "outputTokens", int),
    ]
    for pattern, key, caster in pattern_specs:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        try:
            extracted[key] = caster(match.group(1))
        except (TypeError, ValueError):
            continue
    return _normalize_tuning_settings(extracted) if extracted else {}


def _positive_int(value: object, fallback: int) -> int:
    try:
        candidate = int(value)
    except (TypeError, ValueError):
        return fallback
    return candidate if candidate > 0 else fallback


def _non_negative_int(value: object, fallback: int) -> int:
    try:
        candidate = int(value)
    except (TypeError, ValueError):
        return fallback
    return candidate if candidate >= 0 else fallback


def _integer_value(value: object, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _bounded_float(value: object, fallback: float, *, minimum: float, maximum: float) -> float:
    try:
        candidate = float(value)
    except (TypeError, ValueError):
        return fallback
    if candidate < minimum:
        return minimum
    if candidate > maximum:
        return maximum
    return candidate


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
