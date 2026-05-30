from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import socket
import subprocess
import threading
import time
from typing import Any, Callable
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
from local_ai_control_center_installer.control_center_backend.services import benchmark_service
from local_ai_control_center_installer.control_center_backend.services.server_service import (
    _load_runtime_launch_argument_values,
    _resolve_spec_type_for_runtime,
    load_runtime_diagnostics,
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
_INVALID_MAIN_GPU_RE = re.compile(r"invalid value for main_gpu", re.IGNORECASE)

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


def _path_is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _sanitize_workspace_slug(value: object, fallback: str = "scratch") -> str:
    text = re.sub(r"[^a-z0-9._-]+", "-", str(value or "").strip().lower()).strip("-.")
    return text or fallback


def _default_tuning_workspace_root(config: ControlCenterConfig) -> Path:
    return config.install_root / "workspaces" / "tuning-lab"


def _suggest_tuning_working_directory(
    working_directory: object,
    config: ControlCenterConfig,
    *,
    fallback_slug: str = "scratch",
) -> str:
    raw_value = str(working_directory or "").strip()
    candidate = Path(raw_value).expanduser() if raw_value else config.install_root
    resolved_candidate = candidate.resolve()
    if (
        resolved_candidate == config.install_root
        or _path_is_relative_to(resolved_candidate, config.control_center_config_root)
    ):
        return str((_default_tuning_workspace_root(config) / _sanitize_workspace_slug(fallback_slug)).resolve())
    return str(resolved_candidate)


def _load_tuning_lab_prerequisites(
    config: ControlCenterConfig,
    working_directory: str = "",
) -> dict[str, Any]:
    configured_working_directory = str(working_directory or config.install_root)
    safe_working_directory = _suggest_tuning_working_directory(
        configured_working_directory,
        config,
        fallback_slug="scratch",
    )
    runtime_state = load_runtime_state(config)
    blockers: list[str] = []
    active_binary_path = Path(str(runtime_state.get("active_binary", "") or ""))
    active_model_id = str(runtime_state.get("active_model_id", "") or "").strip().lower()
    active_model_label = str(runtime_state.get("active_model", "") or "").strip().lower()
    active_model_path = Path(str(runtime_state.get("active_model_path", "") or ""))
    opencode_executable_path = _resolve_opencode_executable_path(config)
    opencode_config_path = config.opencode_managed_config_path

    if not active_binary_path.is_file():
        blockers.append("Aktivni runtime binar nije spreman za Tuning Lab.")
    if (
        not active_model_path.is_file()
        or not active_model_id
        or active_model_id == "unknown"
        or active_model_label in {"", "unknown", "nema aktivnog modela"}
    ):
        blockers.append("Aktivan model nije podešen. Aktiviraj model pre pokretanja Tuning Lab-a.")
    if not opencode_executable_path.is_file():
        blockers.append(
            "OpenCode nije instaliran na ovoj mašini. Pokreni installer ponovo sa uključenim OpenCode-om."
        )
    elif not opencode_config_path.is_file():
        blockers.append("OpenCode managed config nedostaje. Pokreni repair ili reinstall OpenCode komponente.")

    return {
        "canQueue": not blockers,
        "runBlockers": blockers,
        "configuredWorkingDirectory": configured_working_directory,
        "workingDirectory": safe_working_directory,
        "workingDirectoryWasAdjusted": safe_working_directory != configured_working_directory,
        "runtimeBinaryReady": active_binary_path.is_file(),
        "activeModelReady": (
            active_model_path.is_file()
            and bool(active_model_id)
            and active_model_id != "unknown"
            and active_model_label not in {"", "unknown", "nema aktivnog modela"}
        ),
        "opencodeReady": opencode_executable_path.is_file() and opencode_config_path.is_file(),
    }


def _build_tuning_workspace_copy_ignore(
    *,
    source_dir: Path,
    config: ControlCenterConfig,
) -> Callable[[str, list[str]], set[str]]:
    ignored_names = {".git", ".pytest_cache", "__pycache__"}
    internal_roots: list[Path] = []
    tuning_internal_root = (config.control_center_config_root / "tuning-lab").resolve()
    if _path_is_relative_to(tuning_internal_root, source_dir):
        internal_roots.append(tuning_internal_root)

    def _ignore(current_dir: str, names: list[str]) -> set[str]:
        ignored = {name for name in names if name in ignored_names}
        current_path = Path(current_dir).resolve()
        for name in names:
            candidate = (current_path / name).resolve()
            if any(candidate == root for root in internal_roots):
                ignored.add(name)
        return ignored

    return _ignore

_BATCH_PRESETS: list[dict[str, Any]] = [
    {
        "id": "game-batch-01",
        "label": "Game Batch 01",
        "summary": "Prvi game benchmark batch: easy, medium i hard browser igra za poređenje tuning setova.",
        "focusAreas": [
            "stabilan throughput na malom scope-u",
            "koherencija kroz više gameplay sistema",
            "višefajlna agentic izdržljivost",
        ],
        "tasks": [
            {
                "id": "jumping-ball-runner",
                "label": "Jumping Ball Runner",
                "difficulty": "easy",
                "goal": "code",
                "summary": "Jedan HTML fajl, endless runner sa score, high score i restart tokom.",
                "scopeLabel": "jedan fajl",
                "focusLabel": "stabilan throughput",
                "expectedArtifact": "index.html",
                "taskPrompt": (
                    "Napravite kompletnu browser igru `Jumping Ball Runner` kao jedan jedini "
                    "`index.html` fajl sa ugrađenim CSS i JavaScript kodom. Igra mora da radi "
                    "lokalno samo otvaranjem `index.html`. Igrač kontroliše lopticu ili lik koji "
                    "skače preko prepreka, cilj je da preživi što duže, a brzina mora postepeno da "
                    "raste. Obavezno dodajte prikaz trenutnog skora, high score, retry ili restart "
                    "dugme, šaren i jasan UI sa parallax pozadinom, tastaturne kontrole i jasna "
                    "stanja start / gameplay / game over. Nema build alata ni framework-a. Na vrhu "
                    "fajla ostavite kratak komentar šta je urađeno i koje su kontrole."
                ),
                "successChecks": [
                    {
                        "label": "HTML postoji",
                        "command": "if (Test-Path index.html) { exit 0 } else { exit 1 }",
                        "kind": "custom",
                    },
                    {
                        "label": "Ključni stringovi postoje",
                        "command": "Select-String -Path index.html -Pattern 'Jumping Ball Runner|High Score|Score' -AllMatches | Out-Null; if ($LASTEXITCODE -eq 0) { exit 0 } else { exit 1 }",
                        "kind": "custom",
                    },
                ],
            },
            {
                "id": "balloon-blaster",
                "label": "Balloon Blaster",
                "difficulty": "medium",
                "goal": "code",
                "summary": "Jedan HTML fajl, shooter sa combo sistemom, power-up-ovima i više nivoa težine.",
                "scopeLabel": "jedan fajl",
                "focusLabel": "koherencija sistema",
                "expectedArtifact": "index.html",
                "taskPrompt": (
                    "Napravite kompletnu browser igru `Balloon Blaster` kao jedan jedini "
                    "`index.html` fajl sa ugrađenim CSS i JavaScript kodom. Shooter je pri dnu "
                    "ekrana, baloni dolaze odozgo i igrač skuplja poene razbijanjem balona. "
                    "Obavezno dodajte tri veličine balona sa različitim poenima, combo sistem, "
                    "najmanje tri power-up mehanike, particle efekte pri pucanju, high score "
                    "sačuvan lokalno i najmanje dva nivoa težine. Kontrole moraju da rade "
                    "tastaturom, a bonus je miš ili touch. Mora da postoje start ekran, gameplay i "
                    "pauza ili jasan game over / restart tok. Nema React-a, build alata ni "
                    "framework-a. Na vrhu fajla dodajte kratak komentar sa opisom igre i kontrola."
                ),
                "successChecks": [
                    {
                        "label": "HTML postoji",
                        "command": "if (Test-Path index.html) { exit 0 } else { exit 1 }",
                        "kind": "custom",
                    },
                    {
                        "label": "Ključni stringovi postoje",
                        "command": "Select-String -Path index.html -Pattern 'Balloon Blaster|Combo|High Score' -AllMatches | Out-Null; if ($LASTEXITCODE -eq 0) { exit 0 } else { exit 1 }",
                        "kind": "custom",
                    },
                ],
            },
            {
                "id": "octopus-invaders",
                "label": "Octopus Invaders",
                "difficulty": "hard",
                "goal": "code",
                "summary": "Višefajlni vanilla JS canvas shooter sa README-jem, modulima i kompletnim game loop-om.",
                "scopeLabel": "više fajlova",
                "focusLabel": "agentic arhitektura",
                "expectedArtifact": "index.html + js/* + README.md",
                "taskPrompt": (
                    "Napravite browser igru `Octopus Invaders` kao višefajlni vanilla JavaScript "
                    "projekat bez framework-a i biblioteka. Obavezna struktura: `index.html`, "
                    "`README.md`, `css/styles.css`, `js/config.js`, `js/game.js`, `js/player.js`, "
                    "`js/enemies.js`, `js/particles.js`, `js/background.js`, `js/ui.js` i "
                    "`js/audio.js`. Igra je vertical space shooter na canvas-u i mora da radi "
                    "lokalno kada se servira prost statički server. Dodajte start ekran, gameplay "
                    "loop, pause, game over, različite neprijatelje, score, health, combo i makar "
                    "jedan boss ili završni veći susret. README mora da objasni šta je igra, kako "
                    "se pokreće, kontrole i strukturu projekta. Cilj je da igra radi iz prve bez "
                    "ručnog dorađivanja."
                ),
                "successChecks": [
                    {
                        "label": "Glavni fajlovi postoje",
                        "command": "$required = @('index.html','README.md','css/styles.css','js/config.js','js/game.js','js/player.js','js/enemies.js','js/particles.js','js/background.js','js/ui.js','js/audio.js'); foreach ($path in $required) { if (-not (Test-Path $path)) { exit 1 } }; exit 0",
                        "kind": "custom",
                    },
                    {
                        "label": "README i index referenca postoje",
                        "command": "Select-String -Path README.md -Pattern 'kontrol|control|pokret' -AllMatches | Out-Null; if ($LASTEXITCODE -ne 0) { exit 1 }; Select-String -Path index.html -Pattern 'styles.css|config.js|game.js' -AllMatches | Out-Null; if ($LASTEXITCODE -eq 0) { exit 0 } else { exit 1 }",
                        "kind": "custom",
                    },
                ],
            },
        ],
    }
]


def load_tuning_lab_summary(
    *,
    history_page: int = 1,
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    resolved_config = config or get_config()
    _reconcile_orphaned_active_run(resolved_config)
    history_items = _load_history(resolved_config)
    page = max(int(history_page or 1), 1)
    total_items = len(history_items)
    total_pages = max((total_items + TUNING_LAB_HISTORY_PAGE_SIZE - 1) // TUNING_LAB_HISTORY_PAGE_SIZE, 1)
    start_index = (page - 1) * TUNING_LAB_HISTORY_PAGE_SIZE
    end_index = start_index + TUNING_LAB_HISTORY_PAGE_SIZE
    run_state = _load_run_state(resolved_config)
    if not run_state["activeRun"]:
        _cleanup_stale_tuning_processes(
            resolved_config,
            active_run=None,
            history_items=history_items,
        )
    effective_settings = load_effective_settings_state(resolved_config)
    runtime_state = load_runtime_state(resolved_config)
    configured_working_directory = str(
        effective_settings.get("workingDirectory", resolved_config.install_root)
    )
    prerequisites = _load_tuning_lab_prerequisites(
        resolved_config,
        configured_working_directory,
    )
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
        "batchPresets": deepcopy(_BATCH_PRESETS),
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
            "workingDirectory": str(prerequisites["workingDirectory"]),
            "configuredWorkingDirectory": str(prerequisites["configuredWorkingDirectory"]),
            "workingDirectoryWasAdjusted": bool(prerequisites["workingDirectoryWasAdjusted"]),
            "canQueue": bool(prerequisites["canQueue"]),
            "runBlockers": list(prerequisites["runBlockers"]),
            "runtimeBinaryReady": bool(prerequisites["runtimeBinaryReady"]),
            "activeModelReady": bool(prerequisites["activeModelReady"]),
            "opencodeReady": bool(prerequisites["opencodeReady"]),
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
    _reconcile_orphaned_active_run(resolved_config)
    run_state = _load_run_state(resolved_config)
    active_run = run_state.get("activeRun")
    return dict(active_run) if isinstance(active_run, dict) else {}


def load_tuning_lab_history_page(
    *,
    page: int = 1,
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    return load_tuning_lab_summary(history_page=page, config=config)


def _reconcile_orphaned_active_run(config: ControlCenterConfig) -> None:
    global _RUNNER_THREAD
    if _RUNNER_THREAD and _RUNNER_THREAD.is_alive():
        return
    with _RUN_LOCK:
        if _RUNNER_THREAD and _RUNNER_THREAD.is_alive():
            return
        run_state = _load_run_state(config)
        active_run = run_state.get("activeRun")
        if not isinstance(active_run, dict):
            return
        status = str(active_run.get("status", "") or "").strip().lower()
        if status in {"completed", "failed"}:
            return
        live_pids = {
            int(record.get("pid", 0) or 0)
            for record in _list_local_process_records()
            if int(record.get("pid", 0) or 0) > 0
        }
        tracked_pids: set[int] = set()
        for slot in active_run.get("slots", []):
            if not isinstance(slot, dict):
                continue
            for key in ("runtimePid", "opencodePid"):
                pid = int(slot.get(key, 0) or 0)
                if pid > 0:
                    tracked_pids.add(pid)
        if not tracked_pids:
            return
        if tracked_pids and tracked_pids.intersection(live_pids):
            return
        reconciled = deepcopy(active_run)
        summary = "Aktivni Tuning Lab run je prekinut tokom restarta panela ili gaÅ¡enja procesa."
        reconciled["status"] = "failed"
        reconciled["finishedAt"] = _now_iso()
        reconciled["suggestedWinnerSlotId"] = None
        reconciled["winnerSummary"] = ""
        reconciled["summary"] = summary
        reconciled["currentPhase"] = "failed"
        reconciled["currentPhaseLabel"] = "Run je prekinut"
        reconciled["currentStepSummary"] = summary
        reconciled["elapsedMs"] = _elapsed_ms_from_started_at(reconciled.get("startedAt"))
        for slot in reconciled.get("slots", []):
            if not isinstance(slot, dict):
                continue
            slot_status = str(slot.get("status", "") or "").strip().lower()
            if slot_status in {"completed", "failed"}:
                continue
            slot["status"] = "failed"
            slot["summary"] = "Run je prekinut pre nego Å¡to je ovaj slot zavrÅ¡io."
        history = _load_history(config)
        history.insert(0, reconciled)
        _save_history(config, history)
        _save_run_state(config, active_run=None, queue=run_state.get("queue", []))


def prepare_tuning_workspace(
    *,
    working_directory: str,
    experiment_id: str,
    slot_id: str,
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    resolved_config = config or get_config()
    source_dir = Path(str(working_directory or resolved_config.install_root)).expanduser()
    if source_dir.exists() and not source_dir.is_dir():
        raise RuntimeError(f"Radni direktorijum nije folder: {source_dir}")
    if not source_dir.exists():
        source_dir.mkdir(parents=True, exist_ok=True)
    source_dir = source_dir.resolve()
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
        ignore=_build_tuning_workspace_copy_ignore(source_dir=source_dir, config=resolved_config),
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
    prerequisites = _load_tuning_lab_prerequisites(
        resolved_config,
        str(payload.get("workingDirectory", "") or ""),
    )
    if not prerequisites["canQueue"]:
        blockers = " ".join(
            str(item).strip() for item in prerequisites["runBlockers"] if str(item).strip()
        )
        return action_result(
            "error",
            "queue-tuning-experiment",
            f"Tuning Lab trenutno nije spreman za pokretanje. {blockers}".strip(),
        )
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


def enqueue_tuning_batch(
    payload: dict[str, Any],
    *,
    config: ControlCenterConfig | None = None,
    start_worker: bool = True,
) -> dict[str, Any]:
    resolved_config = config or get_config()
    preset_id = str(payload.get("presetId", "") or "").strip()
    preset = next((item for item in _BATCH_PRESETS if str(item.get("id", "") or "") == preset_id), None)
    if preset is None:
        return action_result("error", "queue-tuning-batch", "Traženi batch preset nije pronađen.")

    working_directory = str(payload.get("workingDirectory", "") or "").strip()
    prerequisites = _load_tuning_lab_prerequisites(resolved_config, working_directory)
    if not prerequisites["canQueue"]:
        blockers = " ".join(
            str(item).strip() for item in prerequisites["runBlockers"] if str(item).strip()
        )
        return action_result(
            "error",
            "queue-tuning-batch",
            f"Tuning Lab trenutno nije spreman za pokretanje. {blockers}".strip(),
        )
    provided_slots = payload.get("slots") if isinstance(payload.get("slots"), list) else []
    run_ids: list[str] = []

    with _RUN_LOCK:
        run_state = _load_run_state(resolved_config)
        queue = list(run_state["queue"])
        for task in preset.get("tasks", []):
            if not isinstance(task, dict):
                continue
            experiment = _normalize_experiment_payload(
                {
                    "name": f"{preset['label']} · {task.get('label', 'Task')}",
                    "goal": str(task.get("goal", "code") or "code"),
                    "taskPrompt": str(task.get("taskPrompt", "") or ""),
                    "workingDirectory": working_directory,
                    "successChecks": deepcopy(task.get("successChecks", [])),
                    "slots": deepcopy(provided_slots),
                },
                resolved_config,
            )
            queue.append(experiment)
            run_ids.append(str(experiment.get("runId", "") or ""))
        _save_run_state(resolved_config, active_run=run_state["activeRun"], queue=queue)

    if start_worker and run_ids:
        _ensure_tuning_worker(resolved_config)
    return {
        "status": "accepted",
        "summary": f"Batch {preset['label']} je dodat u Tuning Lab red čekanja.",
        "runIds": run_ids,
    }


def run_next_tuning_experiment(
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    resolved_config = config or get_config()
    history_snapshot = _load_history(resolved_config)
    run_state_snapshot = _load_run_state(resolved_config)
    if not run_state_snapshot["activeRun"]:
        _cleanup_stale_tuning_processes(
            resolved_config,
            active_run=None,
            history_items=history_snapshot,
        )
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
    _cleanup_stale_tuning_processes(
        resolved_config,
        active_run=None,
        history_items=_load_history(resolved_config),
    )

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


def resolve_tuning_playable_file(
    run_id: str,
    slot_id: str,
    asset_path: str = "",
    config: ControlCenterConfig | None = None,
) -> Path | None:
    resolved_config = config or get_config()
    playable_root = (
        _tuning_runs_root(resolved_config)
        / str(run_id or "").strip()
        / str(slot_id or "").strip()
        / "playable"
    )
    if not playable_root.is_dir():
        return None
    normalized_asset = _normalize_relative_artifact_path(asset_path) or "index.html"
    candidate = (playable_root / normalized_asset).resolve()
    try:
        candidate.relative_to(playable_root.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


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
    active_run["currentPhase"] = "queue"
    active_run["currentPhaseLabel"] = "Čeka prvi slot"
    active_run["currentStepSummary"] = "Tuning Lab priprema poređenje slotova."
    active_run["currentCheckLabel"] = ""
    active_run["currentLogExcerpt"] = ""
    active_run["currentRawLogExcerpt"] = ""
    active_run["lastUpdatedAt"] = active_run["startedAt"]
    active_run["elapsedMs"] = 0
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
    active_run["currentPhase"] = "completed" if active_run["suggestedWinnerSlotId"] else "failed"
    active_run["currentPhaseLabel"] = (
        "Pobednik je predložen" if active_run["suggestedWinnerSlotId"] else "Nema uspešnog pobednika"
    )
    active_run["currentStepSummary"] = active_run["summary"]
    active_run["currentCheckLabel"] = ""
    active_run["currentLogExcerpt"] = ""
    active_run["currentRawLogExcerpt"] = ""
    active_run["lastUpdatedAt"] = active_run["finishedAt"]
    active_run["elapsedMs"] = _elapsed_ms_from_started_at(active_run.get("startedAt"))
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
    slot_artifact_root = _tuning_runs_root(config) / str(experiment.get("runId", "") or "run") / slot_id
    slot_artifact_root.mkdir(parents=True, exist_ok=True)
    merged_settings = _merge_slot_settings(slot.get("settingsPatch"), config)
    workspace_info: dict[str, Any] = {
        "mode": "",
        "workspacePath": str(slot_artifact_root / "workspace"),
        "cleanupPath": "",
    }
    workspace_path = Path(str(workspace_info["workspacePath"]))
    before_snapshot: dict[str, Any] = {}
    runtime_session: dict[str, Any] | None = None
    runtime_profile: dict[str, Any] | None = None
    opencode_result: dict[str, Any] | None = None
    success_checks: list[dict[str, Any]] = []
    started_at = _now_iso()
    started_monotonic = time.monotonic()
    error_summary = ""

    def update_progress(
        phase: str,
        phase_label: str,
        summary: str,
        *,
        log_excerpt: str = "",
        raw_log_excerpt: str = "",
        check_label: str = "",
        slot_patch: dict[str, Any] | None = None,
    ) -> None:
        experiment["currentPhase"] = phase
        experiment["currentPhaseLabel"] = phase_label
        experiment["currentStepSummary"] = summary
        experiment["currentCheckLabel"] = check_label
        experiment["currentLogExcerpt"] = log_excerpt[-4000:] if log_excerpt else ""
        experiment["currentRawLogExcerpt"] = raw_log_excerpt[-4000:] if raw_log_excerpt else ""
        experiment["lastUpdatedAt"] = _now_iso()
        experiment["elapsedMs"] = _elapsed_ms_from_started_at(experiment.get("startedAt"))
        _update_active_run_slot(
            experiment,
            {
                "status": "running",
                "summary": summary,
                **(slot_patch or {}),
            },
        )
        _write_active_run(config, experiment)

    try:
        update_progress(
            "workspace",
            "Priprema radnog prostora",
            f"{slot_label} priprema izolovani radni prostor za zadatak.",
        )
        workspace_info = prepare_tuning_workspace(
            working_directory=working_directory,
            experiment_id=str(experiment.get("runId", "") or "run"),
            slot_id=slot_id,
            config=config,
        )
        workspace_path = Path(str(workspace_info["workspacePath"]))
        _update_active_run_slot(
            experiment,
            {
                "workspaceMode": str(workspace_info.get("mode", "") or ""),
                "workspacePath": str(workspace_path),
            },
        )
        before_snapshot = _snapshot_directory(workspace_path)
        runtime_session = _launch_slot_runtime(
            slot_settings=merged_settings,
            slot_artifact_root=slot_artifact_root,
            config=config,
        )
        update_progress(
            "runtime",
            "Pokretanje runtime servera",
            f"{slot_label} je podigao runtime i čeka OpenCode task.",
            log_excerpt=_read_text_tail(Path(str(runtime_session.get("logPath", "") or ""))),
            slot_patch={
                "workspaceMode": str(workspace_info.get("mode", "") or ""),
                "workspacePath": str(workspace_path),
                "runtimeCommand": str(runtime_session.get("commandPreview", "") or ""),
                "runtimeBaseUrl": str(runtime_session.get("baseUrl", "") or ""),
                "runtimeDiagnostics": dict(runtime_session.get("runtimeDiagnostics", {}))
                if isinstance(runtime_session.get("runtimeDiagnostics"), dict)
                else {},
                "runtimePid": int(
                    runtime_session.get("runtimePid", 0)
                    or getattr(runtime_session.get("process"), "pid", 0)
                    or 0
                ),
                "runtimeLogPath": str(runtime_session.get("logPath", "") or ""),
            },
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
            progress_callback=update_progress,
            upstream_base_url=str(runtime_session.get("baseUrl", "") or ""),
            runtime_log_path=Path(str(runtime_session.get("logPath", "") or "")),
            runtime_name=str(runtime_session.get("runtimeName", "") or ""),
            launch_arguments=(
                dict(runtime_session.get("launchArguments", {}))
                if isinstance(runtime_session.get("launchArguments"), dict)
                else {}
            ),
        )
        update_progress(
            "checks",
            "Pokretanje success check lanca",
            f"{slot_label} je završio OpenCode task i ulazi u proveru uspeha.",
            log_excerpt=str(opencode_result.get("assistantText", "") if isinstance(opencode_result, dict) else "")[-4000:],
        )
        success_check_specs = _resolve_success_check_specs(
            experiment=experiment,
            workspace_path=workspace_path,
        )
        success_checks = _run_success_checks(
            success_check_specs,
            workspace_path,
            slot_artifact_root,
            progress_callback=update_progress,
        )
    except Exception as exc:  # noqa: BLE001
        error_summary = str(exc)
        update_progress(
            "failed",
            "Run je pao",
            error_summary or f"{slot_label} nije završio eksperiment.",
            log_excerpt=error_summary,
        )
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
    active_slot_snapshot = next(
        (
            candidate
            for candidate in experiment.get("slots", [])
            if isinstance(candidate, dict) and str(candidate.get("id", "") or "") == slot_id
        ),
        {},
    )
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
    playable_artifacts = (
        _preserve_playable_artifacts(
            workspace_path=workspace_path,
            slot_artifact_root=slot_artifact_root,
            changed_files=diff_artifacts["changedFiles"],
        )
        if status == "completed"
        else {}
    )
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
        "diffFiles": diff_artifacts.get("diffFiles", []),
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
        "runtimeDiagnostics": (
            dict(opencode_result.get("runtimeDiagnostics", {}))
            if isinstance(opencode_result, dict) and isinstance(opencode_result.get("runtimeDiagnostics"), dict)
            else dict(active_slot_snapshot.get("runtimeDiagnostics", {}))
            if isinstance(active_slot_snapshot.get("runtimeDiagnostics"), dict)
            else dict(runtime_session.get("runtimeDiagnostics", {}))
            if isinstance(runtime_session, dict) and isinstance(runtime_session.get("runtimeDiagnostics"), dict)
            else {}
        ),
        "runtimePid": int(
            (
                runtime_session.get("runtimePid", 0)
                or getattr(runtime_session.get("process"), "pid", 0)
                or 0
            )
            if isinstance(runtime_session, dict)
            else 0
        ),
        "runtimeLogPath": str(runtime_session.get("logPath", "") if isinstance(runtime_session, dict) else ""),
        "opencodeCommand": str(opencode_result.get("commandPreview", "") if isinstance(opencode_result, dict) else ""),
        "opencodePid": int(
            (
                opencode_result.get("opencodePid", 0)
                or active_slot_snapshot.get("opencodePid", 0)
                or 0
            )
            if isinstance(opencode_result, dict)
            else int(active_slot_snapshot.get("opencodePid", 0) or 0)
        ),
        "stdoutPath": str(
            (
                opencode_result.get("stdoutPath", "")
                or active_slot_snapshot.get("stdoutPath", "")
                or ""
            )
            if isinstance(opencode_result, dict)
            else str(active_slot_snapshot.get("stdoutPath", "") or "")
        ),
        "stderrPath": str(
            (
                opencode_result.get("stderrPath", "")
                or active_slot_snapshot.get("stderrPath", "")
                or ""
            )
            if isinstance(opencode_result, dict)
            else str(active_slot_snapshot.get("stderrPath", "") or "")
        ),
        "liveOutputTokensPerSecond": float(
            (
                opencode_result.get("liveOutputTokensPerSecond", 0.0)
                or active_slot_snapshot.get("liveOutputTokensPerSecond", 0.0)
                or 0.0
            )
            if isinstance(opencode_result, dict)
            else float(active_slot_snapshot.get("liveOutputTokensPerSecond", 0.0) or 0.0)
        ),
        "liveTotalTokensPerSecond": float(
            (
                opencode_result.get("liveTotalTokensPerSecond", 0.0)
                or active_slot_snapshot.get("liveTotalTokensPerSecond", 0.0)
                or 0.0
            )
            if isinstance(opencode_result, dict)
            else float(active_slot_snapshot.get("liveTotalTokensPerSecond", 0.0) or 0.0)
        ),
        "runtimePromptTokensPerSecond": float(
            (
                opencode_result.get("runtimePromptTokensPerSecond", 0.0)
                or active_slot_snapshot.get("runtimePromptTokensPerSecond", 0.0)
                or 0.0
            )
            if isinstance(opencode_result, dict)
            else float(active_slot_snapshot.get("runtimePromptTokensPerSecond", 0.0) or 0.0)
        ),
        "runtimeGenerationTokensPerSecond": float(
            (
                opencode_result.get("runtimeGenerationTokensPerSecond", 0.0)
                or active_slot_snapshot.get("runtimeGenerationTokensPerSecond", 0.0)
                or 0.0
            )
            if isinstance(opencode_result, dict)
            else float(active_slot_snapshot.get("runtimeGenerationTokensPerSecond", 0.0) or 0.0)
        ),
        "runtimePromptSummary": str(
            (
                opencode_result.get("runtimePromptSummary", "")
                or active_slot_snapshot.get("runtimePromptSummary", "")
                or ""
            )
            if isinstance(opencode_result, dict)
            else str(active_slot_snapshot.get("runtimePromptSummary", "") or "")
        ),
        "runtimeGenerationSummary": str(
            (
                opencode_result.get("runtimeGenerationSummary", "")
                or active_slot_snapshot.get("runtimeGenerationSummary", "")
                or ""
            )
            if isinstance(opencode_result, dict)
            else str(active_slot_snapshot.get("runtimeGenerationSummary", "") or "")
        ),
        "runtimeLatestTimingLine": str(
            (
                opencode_result.get("runtimeLatestTimingLine", "")
                or active_slot_snapshot.get("runtimeLatestTimingLine", "")
                or ""
            )
            if isinstance(opencode_result, dict)
            else str(active_slot_snapshot.get("runtimeLatestTimingLine", "") or "")
        ),
        "lastLiveMeasuredAt": str(
            (
                opencode_result.get("lastLiveMeasuredAt", "")
                or active_slot_snapshot.get("lastLiveMeasuredAt", "")
                or ""
            )
            if isinstance(opencode_result, dict)
            else str(active_slot_snapshot.get("lastLiveMeasuredAt", "") or "")
        ),
        "playableEntryPath": str(playable_artifacts.get("playableEntryPath", "") or ""),
        "playableFilesPreserved": int(playable_artifacts.get("playableFilesPreserved", 0) or 0),
    }
    update_progress(
        "slot-finished",
        "Slot je završen",
        summary,
        log_excerpt=(
            str(opencode_result.get("assistantText", "") if isinstance(opencode_result, dict) else "")
            or error_summary
        ),
    )
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
    launch_arguments = _load_runtime_launch_argument_values(
        config,
        runtime_state,
        runtime_name=runtime_name,
        binary_path=binary_path,
    ) | {
        "temperature": float(slot_settings.get("temperature", 0.8)),
        "top_k": int(slot_settings.get("topK", 40)),
        "top_p": float(slot_settings.get("topP", 0.95)),
        "min_p": float(slot_settings.get("minP", 0.05)),
        "repeat_penalty": float(slot_settings.get("repeatPenalty", 1.0)),
        "repeat_last_n": int(slot_settings.get("repeatLastN", 64)),
        "presence_penalty": float(slot_settings.get("presencePenalty", 0.0)),
        "frequency_penalty": float(slot_settings.get("frequencyPenalty", 0.0)),
        "seed": int(slot_settings.get("seed", -1)),
    }
    target = ServerVerificationTarget(
        server_executable=binary_path,
        model_id=model_id,
        model_path=model_path,
        active_model_config_path=config.active_model_config_path,
    )
    context_size = int(slot_settings.get("context", 262144) or 262144)
    command = _build_server_command(
        target,
        port,
        ctx_size=context_size,
        spec_type=spec_type,
        **launch_arguments,
    )
    log_path = slot_artifact_root / "runtime.log"
    process = _launch_background_process(command, log_path)
    fallback_applied = False
    fallback_reason = ""
    if not _wait_for_runtime_ready(base_url, process, timeout_seconds=TUNING_LAB_RUNTIME_READY_TIMEOUT_SECONDS):
        _stop_process(process)
        log_excerpt = log_path.read_text(encoding="utf-8", errors="replace")[-4000:] if log_path.exists() else ""
        if _should_retry_slot_runtime_without_explicit_main_gpu(
            launch_arguments=launch_arguments,
            log_excerpt=log_excerpt,
        ):
            fallback_launch_arguments = dict(launch_arguments)
            fallback_launch_arguments.pop("main_gpu", None)
            fallback_launch_arguments.pop("split_mode", None)
            fallback_command = _build_server_command(
                target,
                port,
                ctx_size=context_size,
                spec_type=spec_type,
                **fallback_launch_arguments,
            )
            process = _launch_background_process(fallback_command, log_path)
            if not _wait_for_runtime_ready(
                base_url,
                process,
                timeout_seconds=TUNING_LAB_RUNTIME_READY_TIMEOUT_SECONDS,
            ):
                _stop_process(process)
                fallback_log_excerpt = (
                    log_path.read_text(encoding="utf-8", errors="replace")[-4000:]
                    if log_path.exists()
                    else ""
                )
                raise RuntimeError(
                    "Tuning Lab runtime nije postao spreman ni posle fallback pokušaja bez "
                    "eksplicitnog `main_gpu` izbora. "
                    + (
                        f"Log: {fallback_log_excerpt}"
                        if fallback_log_excerpt
                        else "Health endpoint nije odgovorio na vreme."
                    )
                )
            launch_arguments = fallback_launch_arguments
            command = fallback_command
            fallback_applied = True
            fallback_reason = (
                "Runtime je odbio eksplicitni `--main-gpu`, pa je Tuning Lab ponovio start "
                "bez `--main-gpu` i `--split-mode`."
            )
        else:
            raise RuntimeError(
                "Tuning Lab runtime nije postao spreman. "
                + (f"Log: {log_excerpt}" if log_excerpt else "Health endpoint nije odgovorio na vreme.")
            )
    runtime_diagnostics = load_runtime_diagnostics(
        runtime_name=runtime_name,
        launch_arguments=launch_arguments,
        log_path=log_path,
    )
    if fallback_applied:
        existing_notes = list(runtime_diagnostics.get("notes", [])) if isinstance(runtime_diagnostics.get("notes"), list) else []
        runtime_diagnostics["notes"] = [fallback_reason, *existing_notes]
        existing_summary = str(runtime_diagnostics.get("summary", "") or "").strip()
        runtime_diagnostics["summary"] = (
            f"{fallback_reason} {existing_summary}".strip()
            if existing_summary
            else fallback_reason
        )
    return {
        "process": process,
        "baseUrl": base_url,
        "commandPreview": subprocess.list2cmdline(command),
        "logPath": str(log_path),
        "runtimeName": runtime_name,
        "launchArguments": launch_arguments,
        "launchFallbackApplied": fallback_applied,
        "launchFallbackReason": fallback_reason,
        "runtimeDiagnostics": runtime_diagnostics,
        "runtimePid": int(getattr(process, "pid", 0) or 0),
    }


def _should_retry_slot_runtime_without_explicit_main_gpu(
    *,
    launch_arguments: dict[str, Any],
    log_excerpt: str,
) -> bool:
    if not isinstance(launch_arguments, dict):
        return False
    if "main_gpu" not in launch_arguments and "split_mode" not in launch_arguments:
        return False
    return bool(_INVALID_MAIN_GPU_RE.search(str(log_excerpt or "")))


def _run_slot_opencode_task(
    *,
    experiment: dict[str, Any],
    slot_settings: dict[str, Any],
    runtime_profile_token: str,
    workspace_path: Path,
    slot_artifact_root: Path,
    config: ControlCenterConfig,
    progress_callback: Callable[..., None] | None = None,
    upstream_base_url: str = "",
    runtime_log_path: Path | None = None,
    runtime_name: str = "",
    launch_arguments: dict[str, Any] | None = None,
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
        "--print-logs",
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
    stdout_path = slot_artifact_root / "opencode-output.jsonl"
    stderr_path = slot_artifact_root / "opencode-error.log"
    slot_label = str(experiment.get("currentSlotLabel", "Aktivni slot") or "Aktivni slot")
    latest_live_metric: dict[str, Any] | None = None
    with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_handle:
        process = subprocess.Popen(
            command,
            cwd=str(workspace_path),
            env=env,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        deadline = started + TUNING_LAB_DEFAULT_TIMEOUT_SECONDS
        while process.poll() is None:
            if time.monotonic() >= deadline:
                _stop_process(process)
                raise RuntimeError("OpenCode task je istekao pre završetka.")
            if upstream_base_url:
                latest_live_metric = benchmark_service.record_runtime_live_slot_metric(
                    upstream_base_url,
                    config=config,
                    label="tuning-lab-live",
                    source="tuning-lab",
                    snapshot_key=f"tuning:{runtime_profile_token or slot_label}",
                )
            runtime_metrics = (
                _extract_runtime_speed_metrics(_read_text_tail(runtime_log_path, limit=4000))
                if runtime_log_path is not None
                else {}
            )
            runtime_diagnostics = load_runtime_diagnostics(
                runtime_name=runtime_name,
                launch_arguments=launch_arguments,
                log_path=runtime_log_path,
            )
            active_slot_snapshot = next(
                (
                    candidate
                    for candidate in experiment.get("slots", [])
                    if isinstance(candidate, dict)
                    and str(candidate.get("id", "") or "") == str(experiment.get("currentSlotId", "") or "")
                ),
                {},
            )
            prompt_tokens_per_second = float(
                runtime_metrics.get("promptTokensPerSecond", 0.0)
                if isinstance(runtime_metrics, dict)
                else 0.0
            ) or float(active_slot_snapshot.get("runtimePromptTokensPerSecond", 0.0) or 0.0)
            generation_tokens_per_second = float(
                runtime_metrics.get("generationTokensPerSecond", 0.0)
                if isinstance(runtime_metrics, dict)
                else 0.0
            ) or float(active_slot_snapshot.get("runtimeGenerationTokensPerSecond", 0.0) or 0.0)
            prompt_summary = str(
                runtime_metrics.get("promptSummary", "")
                if isinstance(runtime_metrics, dict)
                else ""
            ) or str(active_slot_snapshot.get("runtimePromptSummary", "") or "")
            generation_summary = str(
                runtime_metrics.get("generationSummary", "")
                if isinstance(runtime_metrics, dict)
                else ""
            ) or str(active_slot_snapshot.get("runtimeGenerationSummary", "") or "")
            if progress_callback is not None:
                progress_callback(
                    "opencode",
                    "OpenCode task radi",
                    f"{slot_label} trenutno izvršava zadatak nad izolovanim projektom.",
                    log_excerpt=_build_live_opencode_log_excerpt(
                        stdout_path=stdout_path,
                        stderr_path=stderr_path,
                        runtime_prompt_summary=prompt_summary,
                        runtime_generation_summary=generation_summary,
                    ),
                    raw_log_excerpt=_build_debug_opencode_excerpt(
                        stdout_path=stdout_path,
                        stderr_path=stderr_path,
                    ),
                    slot_patch={
                        "workspacePath": str(workspace_path),
                        "runtimeDiagnostics": runtime_diagnostics,
                        "opencodePid": int(getattr(process, "pid", 0) or 0),
                        "opencodeCommand": subprocess.list2cmdline(command),
                        "stdoutPath": str(stdout_path),
                        "stderrPath": str(stderr_path),
                        "liveOutputTokensPerSecond": float(
                            latest_live_metric.get("completionTokensPerSecond", 0.0)
                            if isinstance(latest_live_metric, dict)
                            else 0.0
                        ),
                        "liveTotalTokensPerSecond": float(
                            latest_live_metric.get("totalTokensPerSecond", 0.0)
                            if isinstance(latest_live_metric, dict)
                            else 0.0
                        ),
                        "runtimePromptTokensPerSecond": prompt_tokens_per_second,
                        "runtimeGenerationTokensPerSecond": generation_tokens_per_second,
                        "runtimePromptSummary": prompt_summary,
                        "runtimeGenerationSummary": generation_summary,
                        "runtimeLatestTimingLine": str(
                            runtime_metrics.get("latestLine", "")
                            if isinstance(runtime_metrics, dict)
                            else ""
                        ),
                        "lastLiveMeasuredAt": str(
                            latest_live_metric.get("measuredAt", "")
                            if isinstance(latest_live_metric, dict)
                            else ""
                        ),
                    },
                )
            time.sleep(0.75)
        completed_returncode = int(process.wait())
    total_duration_seconds = max(time.monotonic() - started, 0.001)
    stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.exists() else ""
    stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.exists() else ""
    parsed = _parse_opencode_json_output(stdout_text)
    runtime_metrics = (
        _extract_runtime_speed_metrics(_read_text_tail(runtime_log_path, limit=4000))
        if runtime_log_path is not None
        else {}
    )
    runtime_diagnostics = load_runtime_diagnostics(
        runtime_name=runtime_name,
        launch_arguments=launch_arguments,
        log_path=runtime_log_path,
    )
    output_tokens = int(parsed.get("outputTokens", 0))
    total_tokens = int(parsed.get("totalTokens", 0))
    return {
        "processReturncode": completed_returncode,
        "assistantText": str(parsed.get("assistantText", "") or ""),
        "inputTokens": int(parsed.get("inputTokens", 0)),
        "outputTokens": output_tokens,
        "totalTokens": total_tokens,
        "costUsd": float(parsed.get("costUsd", 0.0)),
        "stdoutPath": str(stdout_path),
        "stderrPath": str(stderr_path),
        "stdoutText": stdout_text,
        "stderrText": stderr_text,
        "commandPreview": subprocess.list2cmdline(command),
        "opencodePid": int(getattr(process, "pid", 0) or 0),
        "averageOutputTokensPerSecond": (output_tokens / total_duration_seconds) if output_tokens > 0 else 0.0,
        "averageTotalTokensPerSecond": (total_tokens / total_duration_seconds) if total_tokens > 0 else 0.0,
        "liveOutputTokensPerSecond": float(
            latest_live_metric.get("completionTokensPerSecond", 0.0)
            if isinstance(latest_live_metric, dict)
            else 0.0
        ),
        "liveTotalTokensPerSecond": float(
            latest_live_metric.get("totalTokensPerSecond", 0.0)
            if isinstance(latest_live_metric, dict)
            else 0.0
        ),
        "runtimePromptTokensPerSecond": float(
            runtime_metrics.get("promptTokensPerSecond", 0.0)
            if isinstance(runtime_metrics, dict)
            else 0.0
        ),
        "runtimeGenerationTokensPerSecond": float(
            runtime_metrics.get("generationTokensPerSecond", 0.0)
            if isinstance(runtime_metrics, dict)
            else 0.0
        ),
        "runtimePromptSummary": str(
            runtime_metrics.get("promptSummary", "")
            if isinstance(runtime_metrics, dict)
            else ""
        ),
        "runtimeGenerationSummary": str(
            runtime_metrics.get("generationSummary", "")
            if isinstance(runtime_metrics, dict)
            else ""
        ),
        "runtimeLatestTimingLine": str(
            runtime_metrics.get("latestLine", "")
            if isinstance(runtime_metrics, dict)
            else ""
        ),
        "runtimeDiagnostics": runtime_diagnostics,
        "lastLiveMeasuredAt": str(
            latest_live_metric.get("measuredAt", "")
            if isinstance(latest_live_metric, dict)
            else ""
        ),
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
    progress_callback: Callable[..., None] | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, check_spec in enumerate(checks, start=1):
        command = str(check_spec.get("command", "") or "").strip()
        if not command:
            continue
        check_label = str(check_spec.get("label", command) or command)
        if progress_callback is not None:
            progress_callback(
                "success-check",
                "Success check radi",
                f"Pokrenut je korak {index}: {check_label}",
                check_label=check_label,
                log_excerpt=command,
            )
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
            "label": check_label,
            "command": command,
            "kind": str(check_spec.get("kind", "custom") or "custom"),
            "returncode": int(completed.returncode),
            "passed": int(completed.returncode) == 0,
            "stdoutPath": str(log_path),
            "stdoutPreview": str(completed.stdout or "")[-1200:],
            "stderrPreview": str(completed.stderr or "")[-1200:],
        }
        if progress_callback is not None:
            progress_callback(
                "success-check-finished",
                "Success check završen",
                (
                    f"Korak {index} je prošao."
                    if result["passed"]
                    else f"Korak {index} je pao i run se zaustavlja."
                ),
                check_label=check_label,
                log_excerpt=result["stdoutPreview"] or result["stderrPreview"] or command,
            )
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
    configured_working_directory = str(
        payload.get("workingDirectory", effective_settings.get("workingDirectory", config.install_root))
        or config.install_root
    ).strip()
    working_directory = _load_tuning_lab_prerequisites(
        config,
        configured_working_directory,
    )["workingDirectory"]
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


def _shorten_log_text(value: object, limit: int = 200) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


def _summarize_opencode_signal_excerpt(output_text: str, *, max_events: int = 4) -> str:
    if not str(output_text or "").strip():
        return ""
    event_lines: list[str] = []
    for raw_line in str(output_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        described = _describe_opencode_event(payload)
        if described:
            event_lines.extend(described)
    return "\n".join(event_lines[-max_events:])


def _describe_opencode_event(payload: dict[str, Any]) -> list[str]:
    event_type = str(payload.get("type", "") or "").strip().lower()
    part = payload.get("part")
    part_payload = part if isinstance(part, dict) else {}
    if event_type == "step_start":
        message_id = str(
            part_payload.get("messageID")
            or part_payload.get("messageId")
            or payload.get("messageID")
            or payload.get("messageId")
            or ""
        ).strip()
        if message_id:
            return [
                "OpenCode je preuzeo zadatak i otvorio novu poruku.",
                f"ID poruke: {message_id}",
            ]
        return ["OpenCode je preuzeo zadatak i zapoceo novi korak."]
    if event_type == "tool_use":
        tool_name = str(part_payload.get("tool", "") or "").strip() or "alat"
        state_payload = part_payload.get("state") if isinstance(part_payload.get("state"), dict) else {}
        status = str(state_payload.get("status", "") or "").strip()
        input_payload = state_payload.get("input") if isinstance(state_payload.get("input"), dict) else {}
        metadata_payload = (
            state_payload.get("metadata") if isinstance(state_payload.get("metadata"), dict) else {}
        )
        file_target = _shorten_log_text(
            input_payload.get("filePath")
            or metadata_payload.get("filepath")
            or part_payload.get("title")
            or ""
        )
        description = _shorten_log_text(
            input_payload.get("description")
            or input_payload.get("command")
            or input_payload.get("text")
            or ""
        )
        prefix = f"Alat {tool_name}"
        if status:
            prefix = f"{prefix} ({status})"
        if tool_name == "write" and file_target:
            file_name = Path(str(file_target)).name or str(file_target)
            return [f"{prefix}: upisan fajl {file_name}"]
        if description:
            return [f"{prefix}: {description}"]
        if file_target:
            return [f"{prefix}: {file_target}"]
        return [prefix]
    if event_type == "text":
        text_value = _shorten_log_text(payload.get("text", ""))
        if text_value:
            return [f"Agent: {text_value}"]
        return []
    if event_type == "step_finish":
        tokens_payload = part_payload.get("tokens")
        tokens = tokens_payload if isinstance(tokens_payload, dict) else {}
        input_tokens = int(tokens.get("input", 0) or 0)
        output_tokens = int(tokens.get("output", 0) or 0)
        total_tokens = int(tokens.get("total", input_tokens + output_tokens) or 0)
        try:
            cost = float(part_payload.get("cost", payload.get("cost", 0.0)) or 0.0)
        except (TypeError, ValueError):
            cost = 0.0
        summary = (
            f"Korak završen: ulaz {input_tokens} | izlaz {output_tokens} | ukupno {total_tokens}"
        )
        if cost > 0:
            summary = f"{summary} | cost {cost:.4f}"
        elif input_tokens or output_tokens or total_tokens:
            summary = f"{summary} | cost 0.0000"
        return [summary]
    return []


def _summarize_opencode_signal_paths(stdout_path: Path, stderr_path: Path) -> str:
    stdout_excerpt = _summarize_opencode_signal_excerpt(_read_text_tail(stdout_path, limit=8000))
    if stdout_excerpt:
        return stdout_excerpt
    stderr_lines = _extract_notable_opencode_stderr_lines(_read_text_tail(stderr_path, limit=2000))
    if stderr_lines:
        return "\n".join(stderr_lines)
    return ""


def _extract_notable_opencode_stderr_lines(stderr_text: str, *, max_lines: int = 4) -> list[str]:
    lines: list[str] = []
    for raw_line in str(stderr_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if line.startswith("INFO "):
            continue
        if "message.part.delta publishing" in lower:
            continue
        if "service=bus" in lower and "publishing" in lower:
            continue
        if "service=db" in lower and "opening database" in lower:
            continue
        if "service=tool.registry" in lower:
            continue
        if lower.startswith("internal plugin info "):
            continue
        if "service=plugin" in lower and " loading" in lower:
            continue
        if "service=lsp" in lower and "disabled" in lower:
            continue
        lines.append(_shorten_log_text(line, limit=220))
    deduped: list[str] = []
    for line in lines:
        if line not in deduped:
            deduped.append(line)
    return deduped[-max_lines:]


def _build_debug_opencode_excerpt(*, stdout_path: Path, stderr_path: Path) -> str:
    lines: list[str] = []
    stdout_excerpt = _summarize_opencode_signal_excerpt(
        _read_text_tail(stdout_path, limit=12000),
        max_events=6,
    )
    if stdout_excerpt:
        lines.extend(line.strip() for line in stdout_excerpt.splitlines() if line.strip())
    stderr_lines = _extract_notable_opencode_stderr_lines(_read_text_tail(stderr_path, limit=4000))
    if stderr_lines:
        lines.append("stderr:")
        lines.extend(stderr_lines)
    if not lines:
        return _shorten_log_text(_read_text_tail(stderr_path, limit=1200), limit=500).strip()
    deduped: list[str] = []
    for line in lines:
        if line not in deduped:
            deduped.append(line)
    return "\n".join(deduped[-10:])


def _build_live_opencode_log_excerpt(
    *,
    stdout_path: Path,
    stderr_path: Path,
    runtime_prompt_summary: str = "",
    runtime_generation_summary: str = "",
) -> str:
    summary = _summarize_opencode_signal_paths(stdout_path, stderr_path)
    lines: list[str] = []
    normalized_summary = str(summary or "").strip()
    if normalized_summary:
        lines.extend([line.strip() for line in normalized_summary.splitlines() if line.strip()])
    if (
        normalized_summary.startswith("OpenCode je preuzeo zadatak")
        and not runtime_prompt_summary
        and not runtime_generation_summary
    ):
        lines.append("OpenCode sesija je otvorena, ali jos nije poslala naredni citljivi korak.")
    if runtime_prompt_summary:
        lines.append(f"Runtime prompt: {runtime_prompt_summary}")
    if runtime_generation_summary:
        lines.append(f"Runtime generacija: {runtime_generation_summary}")
    if not lines:
        return "OpenCode proces je pokrenut i priprema prvi čitljivi događaj."
    deduped: list[str] = []
    for line in lines:
        if line not in deduped:
            deduped.append(line)
    return "\n".join(deduped[-6:])


def _extract_runtime_speed_metrics(log_text: str) -> dict[str, object]:
    latest_prompt_speed = 0.0
    latest_generation_speed = 0.0
    latest_prompt_summary = ""
    latest_generation_summary = ""
    latest_line = ""
    prompt_pattern = re.compile(
        r"slot print_timing:.*?\|\s*([^,|]+),\s*n_tokens\s*=\s*(\d+).*?/\s*([0-9]+(?:\.[0-9]+)?)\s+tokens per second",
        flags=re.IGNORECASE,
    )
    generation_pattern = re.compile(
        r"slot print_timing:.*?n_decoded\s*=\s*(\d+),\s*tg\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*t/s",
        flags=re.IGNORECASE,
    )
    for raw_line in str(log_text or "").splitlines():
        line = raw_line.strip()
        if not line or "slot print_timing:" not in line:
            continue
        latest_line = line
        generation_match = generation_pattern.search(line)
        if generation_match:
            token_count = int(generation_match.group(1) or 0)
            tokens_per_second = float(generation_match.group(2) or 0.0)
            latest_generation_speed = tokens_per_second
            latest_generation_summary = f"generacija | {token_count} tokena | {tokens_per_second:.2f} tok/s"
            continue
        prompt_match = prompt_pattern.search(line)
        if not prompt_match:
            continue
        phase = str(prompt_match.group(1) or "").strip().lower()
        token_count = int(prompt_match.group(2) or 0)
        tokens_per_second = float(prompt_match.group(3) or 0.0)
        summary = f"{phase} | {token_count} tokena | {tokens_per_second:.2f} tok/s"
        if "prompt" in phase:
            latest_prompt_speed = tokens_per_second
            latest_prompt_summary = summary
        else:
            latest_generation_speed = tokens_per_second
            latest_generation_summary = summary
    return {
        "promptTokensPerSecond": latest_prompt_speed,
        "generationTokensPerSecond": latest_generation_speed,
        "promptSummary": latest_prompt_summary,
        "generationSummary": latest_generation_summary,
        "latestLine": latest_line,
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
    before_snapshot: dict[str, Any],
    after_snapshot: dict[str, Any],
    workspace_path: Path,
) -> dict[str, Any]:
    changed_files = sorted(
        path
        for path in set(before_snapshot.keys()) | set(after_snapshot.keys())
        if before_snapshot.get(path) != after_snapshot.get(path)
    )
    summary = "Bez izmena" if not changed_files else f"{len(changed_files)} fajl(ova) je promenjeno."
    diff_blocks: list[str] = []
    diff_files: list[dict[str, Any]] = []
    for relative_path in changed_files[:TUNING_LAB_DIFF_FILE_LIMIT]:
        before_lines = _read_snapshot_text(before_snapshot, workspace_path, relative_path)
        after_lines = _read_snapshot_text(after_snapshot, workspace_path, relative_path)
        if before_lines is None or after_lines is None:
            diff_text = f"*** {relative_path}\n(binarni ili prevelik fajl)\n"
            diff_blocks.append(diff_text)
            diff_files.append(
                {
                    "path": relative_path,
                    "summary": f"{relative_path} (binarni ili prevelik fajl)",
                    "diffText": diff_text,
                    "isBinary": True,
                    "isTruncated": False,
                }
            )
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
            is_truncated = len(diff_lines) > TUNING_LAB_DIFF_LINES_LIMIT
            diff_text = "\n".join(diff_lines[:TUNING_LAB_DIFF_LINES_LIMIT])
            diff_blocks.append(diff_text)
            diff_files.append(
                {
                    "path": relative_path,
                    "summary": relative_path,
                    "diffText": diff_text,
                    "isBinary": False,
                    "isTruncated": is_truncated,
                }
            )
    return {
        "changedFiles": changed_files,
        "summary": summary,
        "diffFiles": diff_files,
        "diffText": "\n\n".join(diff_blocks).strip(),
    }


def _preserve_playable_artifacts(
    *,
    workspace_path: Path,
    slot_artifact_root: Path,
    changed_files: list[str],
) -> dict[str, Any]:
    playable_entry_path = _detect_playable_entry_path(workspace_path, changed_files)
    if not playable_entry_path:
        return {}
    playable_root = slot_artifact_root / "playable"
    shutil.rmtree(playable_root, ignore_errors=True)
    playable_root.mkdir(parents=True, exist_ok=True)
    files_to_copy: list[str] = []

    def add_copy_target(relative_path: str) -> None:
        normalized = _normalize_relative_artifact_path(relative_path)
        if normalized and normalized not in files_to_copy:
            files_to_copy.append(normalized)

    add_copy_target(playable_entry_path)
    for relative_path in changed_files:
        add_copy_target(relative_path)
    for relative_path in _extract_local_html_asset_paths(workspace_path, playable_entry_path):
        add_copy_target(relative_path)

    copied_files = 0
    for relative_path in files_to_copy:
        source_path = workspace_path / Path(relative_path)
        if not source_path.is_file():
            continue
        target_path = playable_root / Path(relative_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        copied_files += 1

    if not (playable_root / Path(playable_entry_path)).is_file():
        shutil.rmtree(playable_root, ignore_errors=True)
        return {}
    return {
        "playableEntryPath": playable_entry_path,
        "playableFilesPreserved": copied_files,
    }


def _detect_playable_entry_path(workspace_path: Path, changed_files: list[str]) -> str:
    candidates: list[str] = []
    if (workspace_path / "index.html").is_file():
        candidates.append("index.html")
    for relative_path in changed_files:
        normalized = _normalize_relative_artifact_path(relative_path)
        if normalized and normalized.lower().endswith(".html"):
            candidates.append(normalized)
    for candidate in candidates:
        if (workspace_path / Path(candidate)).is_file():
            return candidate
    return ""


def _extract_local_html_asset_paths(workspace_path: Path, entry_path: str) -> list[str]:
    html_path = workspace_path / Path(entry_path)
    if not html_path.is_file():
        return []
    try:
        html_text = html_path.read_text(encoding="utf-8")
    except OSError:
        return []
    root_path = workspace_path.resolve()
    discovered: list[str] = []
    for match in re.finditer(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", html_text, flags=re.IGNORECASE):
        raw_value = str(match.group(1) or "").strip()
        if not raw_value:
            continue
        lowered = raw_value.lower()
        if lowered.startswith(("http://", "https://", "//", "data:", "#", "mailto:", "javascript:")):
            continue
        cleaned = raw_value.split("#", 1)[0].split("?", 1)[0].strip()
        normalized = _normalize_relative_artifact_path(cleaned)
        if not normalized:
            continue
        candidate = (html_path.parent / Path(normalized)).resolve()
        try:
            relative = candidate.relative_to(root_path)
        except ValueError:
            continue
        if candidate.is_file():
            relative_path = relative.as_posix()
            if relative_path not in discovered:
                discovered.append(relative_path)
    return discovered


def _normalize_relative_artifact_path(relative_path: str) -> str:
    raw_value = str(relative_path or "").replace("\\", "/").strip().lstrip("/")
    if not raw_value:
        return ""
    path = Path(raw_value)
    if path.is_absolute():
        return ""
    if any(part in ("", ".", "..") for part in path.parts):
        return ""
    return path.as_posix()


def _snapshot_directory(root: Path) -> dict[str, Any]:
    if not root.exists():
        return {}
    snapshot: dict[str, Any] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.parts:
            continue
        try:
            relative = path.relative_to(root).as_posix()
            raw_bytes = path.read_bytes()
            digest = hashlib.sha1(raw_bytes).hexdigest()  # noqa: S324 - non-security diff fingerprint
        except OSError:
            continue
        text_value: str | None = None
        if len(raw_bytes) <= TUNING_LAB_DIFF_FILE_BYTES_LIMIT:
            try:
                text_value = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text_value = None
        snapshot[relative] = {
            "digest": digest,
            "text": text_value,
            "size": len(raw_bytes),
        }
    return snapshot


def _read_snapshot_text(
    snapshot: dict[str, Any],
    workspace_path: Path,
    relative_path: str,
) -> list[str] | None:
    entry = snapshot.get(relative_path)
    if entry is None:
        return []
    if isinstance(entry, dict):
        text_value = entry.get("text")
        if text_value is None:
            return None
        return str(text_value).splitlines()
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


def _update_active_run_slot(active_run: dict[str, Any], patch: dict[str, Any]) -> None:
    current_slot_id = str(active_run.get("currentSlotId", "") or "").strip()
    if not current_slot_id:
        return
    slots = active_run.get("slots")
    if not isinstance(slots, list):
        return
    for candidate in slots:
        if not isinstance(candidate, dict):
            continue
        if str(candidate.get("id", "") or "").strip() != current_slot_id:
            continue
        candidate.update({key: value for key, value in patch.items() if value not in (None, "")})
        break


def _read_text_tail(path: Path, limit: int = 2000) -> str:
    char_limit = max(int(limit or 0), 0)
    if char_limit <= 0:
        return ""
    try:
        file_size = path.stat().st_size
        if file_size <= 0:
            return ""
        byte_window = max(char_limit * 4, 4096)
        read_offset = max(file_size - byte_window, 0)
        with path.open("rb") as handle:
            handle.seek(read_offset)
            raw_bytes = handle.read()
    except OSError:
        return ""
    return raw_bytes.decode("utf-8", errors="replace")[-char_limit:]


def _elapsed_ms_from_started_at(started_at: object) -> int:
    if not isinstance(started_at, str) or not started_at.strip():
        return 0
    try:
        started = datetime.fromisoformat(started_at)
    except ValueError:
        return 0
    return max(int((datetime.now(UTC) - started).total_seconds() * 1000), 0)


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
    if not path.exists() or not path.is_dir():
        return None
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


def _extract_runtime_port_from_base_url(base_url: object) -> int | None:
    match = re.search(r":(\d+)(?:/|$)", str(base_url or "").strip())
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def _extract_port_from_command_line(command_line: object) -> int | None:
    match = re.search(r"--port\s+(\d+)", str(command_line or ""))
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def _list_local_process_records() -> list[dict[str, Any]]:
    if os.name == "nt":
        script = (
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.Name -in @('llama-server.exe','opencode.exe') } | "
            "Select-Object ProcessId, Name, CommandLine | ConvertTo-Json -Compress"
        )
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            return []
        output = str(completed.stdout or "").strip()
        if not output:
            return []
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            return []
        items = payload if isinstance(payload, list) else [payload]
        records: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            records.append(
                {
                    "pid": int(item.get("ProcessId", 0) or 0),
                    "name": str(item.get("Name", "") or ""),
                    "commandLine": str(item.get("CommandLine", "") or ""),
                }
            )
        return records
    completed = subprocess.run(
        ["ps", "-eo", "pid=,comm=,args="],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return []
    records: list[dict[str, Any]] = []
    for raw_line in completed.stdout.splitlines():
        columns = raw_line.strip().split(None, 2)
        if len(columns) < 3:
            continue
        try:
            pid = int(columns[0])
        except ValueError:
            continue
        records.append({"pid": pid, "name": columns[1], "commandLine": columns[2]})
    return records


def _kill_process_tree(pid: int) -> bool:
    normalized_pid = int(pid or 0)
    if normalized_pid <= 0:
        return False
    if os.name == "nt":
        completed = subprocess.run(
            ["taskkill", "/PID", str(normalized_pid), "/T", "/F"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        output = f"{completed.stdout}\n{completed.stderr}".lower()
        return completed.returncode == 0 or "not found" in output or "not running" in output
    try:
        os.kill(normalized_pid, signal.SIGTERM)
    except OSError:
        return False
    return True


def _cleanup_stale_tuning_processes(
    config: ControlCenterConfig,
    *,
    active_run: dict[str, Any] | None = None,
    history_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if active_run:
        return {"killedPids": []}
    runtime_state = load_runtime_state(config)
    main_runtime_port = int(runtime_state.get("port", 0) or 0)
    tuning_root = str(_tuning_runs_root(config).resolve()).lower()
    install_root = str(config.install_root.resolve()).lower()
    stale_ports: set[int] = set()
    for item in history_items or _load_history(config):
        if not isinstance(item, dict):
            continue
        slots = item.get("slots")
        if not isinstance(slots, list):
            continue
        for slot in slots:
            if not isinstance(slot, dict):
                continue
            port = _extract_runtime_port_from_base_url(slot.get("runtimeBaseUrl", ""))
            if port and port != main_runtime_port:
                stale_ports.add(port)
    killed: list[int] = []
    for process in _list_local_process_records():
        pid = int(process.get("pid", 0) or 0)
        name = str(process.get("name", "") or "").strip().lower()
        command_line = str(process.get("commandLine", "") or "")
        if pid <= 0 or not command_line:
            continue
        if name == "opencode.exe" and tuning_root in command_line.lower():
            if _kill_process_tree(pid):
                killed.append(pid)
            continue
        if name != "llama-server.exe":
            continue
        port = _extract_port_from_command_line(command_line)
        if not port or port == main_runtime_port:
            continue
        if port in stale_ports or install_root in command_line.lower():
            if _kill_process_tree(pid):
                killed.append(pid)
    return {"killedPids": killed}


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
