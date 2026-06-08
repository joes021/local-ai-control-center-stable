from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import shlex
import tempfile
import threading
import time

from local_ai_control_center_installer.control_center_backend.config import (
    ControlCenterConfig,
    get_config,
)
from local_ai_control_center_installer.control_center_backend.services.state_helpers import (
    atomic_write_json,
    read_json_object,
)
from local_ai_control_center_installer.control_center_backend.services.server_service import (
    ensure_runtime_ready,
)
from local_ai_control_center_installer.control_center_backend.services.settings_service import (
    apply_opencode_settings,
    delete_opencode_step_preset,
    load_effective_settings_state,
    load_opencode_step_schema,
    save_opencode_step_preset,
)
from local_ai_control_center_installer.control_center_backend.services.status_service import (
    load_runtime_state,
)
from local_ai_control_center_installer.download_plan import (
    OPENCODE_ARTIFACT_DOWNLOAD_KEY,
    DownloadPlan,
    DownloadPlanItem,
)
from local_ai_control_center_installer.downloads import download_file
from local_ai_control_center_installer.opencode_bootstrap import (
    apply_opencode_bootstrap,
    load_opencode_manifest,
)
from local_ai_control_center_installer.platform_paths import (
    is_windows_platform,
    new_console_subprocess_creationflags,
)
from local_ai_control_center_installer.runtime_bootstrap import load_runtime_endpoint_config
from local_ai_control_center_installer.session import InstallerSession


OPENCODE_DISPOSABLE_WORKSPACE_PREFIXES: dict[str, str] = {
    "gui-copy-": "copy",
    "gui-scratch-": "scratch",
    "gui-worktree-": "git-worktree",
}
OPENCODE_HYGIENE_POLL_SECONDS = 15 * 60.0
_HYGIENE_SCHEDULER_LOCK = threading.Lock()
_HYGIENE_SCHEDULER_THREAD: threading.Thread | None = None
_HYGIENE_SCHEDULER_STOP = threading.Event()


def load_opencode_status_payload(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    executable_path = _resolve_opencode_executable_path(config)
    desktop_executable_path = _resolve_windows_opencode_desktop_executable_path(config)
    config_path = config.install_root / "config" / "opencode" / "managed-config.json"
    launcher_path = config.install_root / "control-center" / (
        "Open-OpenCode.cmd" if is_windows_platform() else "Open-OpenCode.sh"
    )
    instances = detect_opencode_instances(executable_path)
    desktop_instances = detect_opencode_desktop_instances(desktop_executable_path)
    launcher_instances = detect_opencode_launcher_instances(launcher_path)
    settings = load_effective_settings_state(config)
    runtime_state = load_runtime_state(config)
    runtime_connected = str(runtime_state.get("runtime_live_status", "")) == "started"
    session_state, session_summary = _build_session_state(
        has_instances=bool(instances),
        has_desktop_instances=bool(desktop_instances),
        launch_in_progress=bool(launcher_instances),
        runtime_connected=runtime_connected,
        runtime_reason=str(runtime_state.get("runtime_live_reason", "") or ""),
    )
    can_open, open_action_label, open_blocked_reason = _resolve_open_action_contract(
        available=executable_path.is_file(),
        config_exists=config_path.is_file(),
        session_state=session_state,
    )
    can_bootstrap, bootstrap_action_label, bootstrap_blocked_reason = _build_bootstrap_action_contract(
        config=config,
        available=executable_path.is_file(),
        config_exists=config_path.is_file(),
        runtime_state=runtime_state,
    )

    return {
        "available": executable_path.is_file(),
        "desktopAvailable": bool(desktop_executable_path and desktop_executable_path.is_file()),
        "desktopExecutablePath": str(desktop_executable_path) if desktop_executable_path else "",
        "active": bool(instances or desktop_instances),
        "instanceCount": len(instances) + len(desktop_instances),
        "instances": desktop_instances + instances,
        "runtimeConnected": runtime_connected,
        "runtimeLiveStatus": str(runtime_state.get("runtime_live_status", "") or ""),
        "runtimeLiveReason": str(runtime_state.get("runtime_live_reason", "") or ""),
        "sessionState": session_state,
        "sessionSummary": session_summary,
        "canOpen": can_open,
        "openActionLabel": open_action_label,
        "openBlockedReason": open_blocked_reason,
        "canBootstrap": can_bootstrap,
        "bootstrapActionLabel": bootstrap_action_label,
        "bootstrapBlockedReason": bootstrap_blocked_reason,
        "configExists": config_path.is_file(),
        "configPath": str(config_path),
        "configDir": str(config_path.parent),
        "executablePath": str(executable_path),
        "workingDirectory": str(settings["workingDirectory"]),
        "buildSteps": int(settings["buildSteps"]),
        "planSteps": int(settings["planSteps"]),
        "generalSteps": int(settings["generalSteps"]),
        "exploreSteps": int(settings["exploreSteps"]),
        "securityMode": str(settings["securityMode"]),
        "securityModeLabel": _security_mode_label(str(settings["securityMode"])),
        "capabilityMode": str(settings["capabilityMode"]),
        "capabilityModeLabel": _capability_mode_label(str(settings["capabilityMode"])),
        "profile": str(settings["profile"]),
        "webSearchMode": str(settings.get("webSearchMode", "off") or "off"),
        "webSearchPromptPrefix": str(settings.get("webSearchPromptPrefix", "/web") or "/web"),
        "localProviderUsesSearchProxy": True,
        "localProviderSearchSummary": _build_local_provider_search_summary(settings),
        "launchPreview": _build_opencode_launch_preview(
            config=config,
            executable_path=executable_path,
            desktop_executable_path=desktop_executable_path,
            managed_config_path=config_path,
            settings=settings,
        ),
        "auditRiskLevel": "",
        "auditSummary": (
            "Installer-managed OpenCode bootstrap je spreman."
            if executable_path.is_file()
            else "OpenCode nije instaliran."
        ),
    }


def bootstrap_opencode_payload(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    runtime_state = load_runtime_state(config)
    can_bootstrap, action_label, blocked_reason = _build_bootstrap_action_contract(
        config=config,
        available=_resolve_opencode_executable_path(config).is_file(),
        config_exists=config.opencode_managed_config_path.is_file(),
        runtime_state=runtime_state,
    )
    if not can_bootstrap:
        return _result(
            "error",
            "bootstrap-opencode",
            blocked_reason or f"{action_label} trenutno nije dostupan.",
        )

    session = InstallerSession(
        install_opencode=True,
        server_verification_status="ready",
        install_root=str(config.install_root),
        verified_server_url=config.ui_url,
        runtime_endpoint_config_path=str(config.runtime_endpoint_config_path),
        active_model_config_path=str(config.active_model_config_path),
    )
    session.download_plan = _build_opencode_bootstrap_download_plan()
    temp_root = Path(tempfile.gettempdir())
    updated = apply_opencode_bootstrap(
        session,
        temp_root=temp_root,
        download_archive=lambda url, destination, *, plan_item=None: download_file(
            url,
            destination,
            plan_item=plan_item,
        ),
    )
    if updated.opencode_artifact_status != "ready" or updated.last_successful_step != "opencode-config":
        summary = str(
            updated.error_message
            or "OpenCode bootstrap nije uspeo."
        ).strip() or "OpenCode bootstrap nije uspeo."
        if updated.failing_step:
            summary = f"{summary} Korak: {updated.failing_step}."
        return _result("error", "bootstrap-opencode", summary)

    try:
        prepare_opencode_launcher(config=config)
    except (FileNotFoundError, OSError):
        return _result(
            "error",
            "bootstrap-opencode",
            "OpenCode artifact je preuzet, ali launcher nije mogao da se pripremi.",
        )

    if _resolve_opencode_executable_path(config).is_file():
        return _result(
            "ok",
            "bootstrap-opencode",
            "OpenCode je instaliran ili popravljen i spreman za Tuning Lab i OpenCode tab.",
        )
    return _result("error", "bootstrap-opencode", "OpenCode executable i dalje nije pronađen posle bootstrap-a.")


def load_opencode_workspace_hygiene_payload(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    workspace_root = _resolve_opencode_workspace_root(config)
    workspace_root.mkdir(parents=True, exist_ok=True)
    process_instances = [*_query_opencode_processes(), *_query_opencode_desktop_processes()]
    active_paths = _collect_active_opencode_workspace_paths(
        workspace_root=workspace_root,
        instances=process_instances,
    )
    protect_most_recent = bool(process_instances) and not active_paths
    items = _scan_opencode_disposable_workspaces(
        workspace_root=workspace_root,
        active_paths=active_paths,
        protect_most_recent=protect_most_recent,
    )
    cleanup_candidates = [item for item in items if bool(item.get("cleanupEligible"))]
    active_items = [item for item in items if bool(item.get("isActive"))]
    protected_recent_items = [item for item in items if bool(item.get("isRecentFallbackProtected"))]
    cleanup_candidate_bytes = sum(int(item.get("sizeBytes", 0) or 0) for item in cleanup_candidates)
    summary = (
        "Nema zaostalih izolovanih OpenCode workspace foldera za čišćenje."
        if not cleanup_candidates
        else (
            f"Pronađeno je {len(cleanup_candidates)} disposable OpenCode workspace foldera "
            f"spremnih za čišćenje ({_format_storage_size(cleanup_candidate_bytes)})."
        )
    )
    return {
        "workspaceRoot": str(workspace_root),
        "summary": summary,
        "canCleanup": bool(cleanup_candidates),
        "disposableWorkspaceCount": len(items),
        "activeWorkspaceCount": len(active_items),
        "recentFallbackProtectedCount": len(protected_recent_items),
        "cleanupCandidateCount": len(cleanup_candidates),
        "cleanupCandidateBytes": cleanup_candidate_bytes,
        "cleanupCandidateSizeLabel": _format_storage_size(cleanup_candidate_bytes),
        "items": items,
        "manualReviewLocations": _build_manual_storage_review_locations(),
        "lastAutoCleanup": load_last_opencode_auto_cleanup_state(config),
    }


def cleanup_opencode_workspace_hygiene_payload(
    config: ControlCenterConfig | None = None,
    *,
    persist_auto_state: bool = False,
    origin: str = "manual",
) -> dict[str, object]:
    config = config or get_config()
    hygiene = load_opencode_workspace_hygiene_payload(config)
    workspace_root = _resolve_opencode_workspace_root(config)
    removed_count = 0
    freed_bytes = 0
    failed_items: list[str] = []
    for item in hygiene.get("items", []):
        if not isinstance(item, dict) or not bool(item.get("cleanupEligible")):
            continue
        candidate_path = Path(str(item.get("path", "") or ""))
        if not _is_opencode_workspace_cleanup_target(candidate_path, workspace_root):
            failed_items.append(f"{candidate_path.name}: putanja nije bezbedna za cleanup")
            continue
        try:
            _remove_tree(candidate_path)
        except OSError as exc:
            failed_items.append(f"{candidate_path.name}: {exc}")
            continue
        removed_count += 1
        freed_bytes += int(item.get("sizeBytes", 0) or 0)

    updated_hygiene = load_opencode_workspace_hygiene_payload(config)
    if failed_items:
        summary = (
            f"Očišćeno: {removed_count} workspace foldera ({_format_storage_size(freed_bytes)}), "
            f"ali {len(failed_items)} stavki nije moglo da se obriše."
        )
        payload = _result("error", "cleanup-opencode-workspaces", summary)
    else:
        summary = (
            "Nije bilo disposable OpenCode workspace foldera za čišćenje."
            if removed_count == 0
            else f"Očišćeno je {removed_count} disposable OpenCode workspace foldera ({_format_storage_size(freed_bytes)})."
        )
        payload = _result("ok", "cleanup-opencode-workspaces", summary)
    payload["cleanup"] = {
        "removedCount": removed_count,
        "freedBytes": freed_bytes,
        "freedSizeLabel": _format_storage_size(freed_bytes),
        "failedCount": len(failed_items),
        "failedItems": failed_items,
    }
    payload["hygiene"] = updated_hygiene
    if persist_auto_state:
        _record_opencode_auto_cleanup_state(
            config,
            {
                "hasRun": True,
                "origin": origin,
                "status": str(payload.get("status", "") or "ok"),
                "summary": str(payload.get("summary", "") or ""),
                "completedAt": _now_iso(),
                "removedCount": removed_count,
                "freedBytes": freed_bytes,
                "freedSizeLabel": _format_storage_size(freed_bytes),
                "failedCount": len(failed_items),
            },
        )
        payload["hygiene"] = load_opencode_workspace_hygiene_payload(config)
    return payload


def run_opencode_hygiene_auto_cleanup(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    try:
        return cleanup_opencode_workspace_hygiene_payload(
            config,
            persist_auto_state=True,
            origin="auto",
        )
    except Exception as exc:  # noqa: BLE001 - scheduler path must persist state even on failure
        summary = f"Auto-cleanup OpenCode workspace-a nije uspeo: {exc}"
        _record_opencode_auto_cleanup_state(
            config,
            {
                "hasRun": True,
                "origin": "auto",
                "status": "error",
                "summary": summary,
                "completedAt": _now_iso(),
                "removedCount": 0,
                "freedBytes": 0,
                "freedSizeLabel": "0 B",
                "failedCount": 1,
            },
        )
        raise


def load_last_opencode_auto_cleanup_state(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    payload = read_json_object(config.opencode_hygiene_state_path)
    if not payload:
        return {
            "hasRun": False,
            "origin": "auto",
            "status": "idle",
            "summary": "Auto-cleanup još nije radio od poslednjeg poznatog stanja.",
            "completedAt": "",
            "removedCount": 0,
            "freedBytes": 0,
            "freedSizeLabel": "0 B",
            "failedCount": 0,
        }
    return {
        "hasRun": bool(payload.get("hasRun", True)),
        "origin": str(payload.get("origin", "auto") or "auto"),
        "status": str(payload.get("status", "idle") or "idle"),
        "summary": str(payload.get("summary", "") or ""),
        "completedAt": str(payload.get("completedAt", "") or ""),
        "removedCount": int(payload.get("removedCount", 0) or 0),
        "freedBytes": int(payload.get("freedBytes", 0) or 0),
        "freedSizeLabel": str(payload.get("freedSizeLabel", "0 B") or "0 B"),
        "failedCount": int(payload.get("failedCount", 0) or 0),
    }


def start_opencode_hygiene_scheduler() -> None:
    global _HYGIENE_SCHEDULER_THREAD
    with _HYGIENE_SCHEDULER_LOCK:
        if _HYGIENE_SCHEDULER_THREAD and _HYGIENE_SCHEDULER_THREAD.is_alive():
            return
        _HYGIENE_SCHEDULER_STOP.clear()
        _HYGIENE_SCHEDULER_THREAD = threading.Thread(
            target=_opencode_hygiene_scheduler_loop,
            name="lacc-opencode-hygiene",
            daemon=True,
        )
        _HYGIENE_SCHEDULER_THREAD.start()


def stop_opencode_hygiene_scheduler() -> None:
    _HYGIENE_SCHEDULER_STOP.set()


def _opencode_hygiene_scheduler_loop() -> None:
    while True:
        try:
            run_opencode_hygiene_auto_cleanup()
        except Exception:  # noqa: BLE001 - auto cleanup loop must stay alive
            time.sleep(1.0)
        if _HYGIENE_SCHEDULER_STOP.wait(OPENCODE_HYGIENE_POLL_SECONDS):
            break


def open_opencode(
    profile: str = "",
    launch_mode: str = "direct",
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    executable_path = _resolve_opencode_executable_path(config)
    desktop_executable_path = _resolve_windows_opencode_desktop_executable_path(config)
    managed_config_path = config.install_root / "config" / "opencode" / "managed-config.json"
    settings = load_effective_settings_state(config)
    normalized_launch_mode = _normalize_opencode_launch_mode(launch_mode)
    if not executable_path.is_file():
        return _result("error", "open-opencode", "OpenCode executable nije pronađen.")
    if not managed_config_path.is_file():
        return _result("error", "open-opencode", "OpenCode managed config nije pronađen.")
    runtime_result = ensure_runtime_ready(config)
    if runtime_result.get("status") != "ok":
        summary = str(runtime_result.get("summary", "") or "Runtime nije spreman za OpenCode.")
        return _result(
            "error",
            "open-opencode",
            f"OpenCode nije pokrenut. {summary}",
        )

    working_directory = _resolve_opencode_working_directory(settings=settings, config=config)
    try:
        workspace_info = (
            _prepare_isolated_opencode_workspace(config=config, working_directory=working_directory)
            if normalized_launch_mode == "isolated"
            else None
        )
    except Exception as exc:
        return _result(
            "error",
            "open-opencode",
            f"Izolovani workspace nije mogao da se pripremi. {exc}",
        )
    project_path = Path(str(workspace_info["workspacePath"])) if workspace_info else working_directory

    existing_desktop_instances = (
        []
        if normalized_launch_mode != "direct"
        else detect_opencode_desktop_instances(desktop_executable_path)
    )
    if existing_desktop_instances:
        return _result(
            "ok",
            "open-opencode",
            "OpenCode GUI je već otvoren; koristi postojeći prozor.",
        )
    existing_instances = [] if normalized_launch_mode != "direct" else detect_opencode_instances(executable_path)
    if existing_instances:
        return _result(
            "ok",
            "open-opencode",
            "OpenCode je već otvoren; backend je pripremljen za postojeću sesiju.",
        )

    if desktop_executable_path and desktop_executable_path.is_file():
        env = _build_opencode_launch_environment(
            managed_config_path=managed_config_path,
            settings=settings,
            profile=profile,
        )
        _launch_opencode_desktop(
            desktop_executable_path=desktop_executable_path,
            working_directory=project_path,
            project_path=project_path,
            env=env,
        )
        return _result(
            "ok",
            "open-opencode",
            _build_opencode_open_summary(
                launch_mode=normalized_launch_mode,
                project_path=project_path,
                workspace_info=workspace_info,
                gui=True,
            ),
        )

    launcher_name_override = None
    if normalized_launch_mode == "isolated":
        launcher_name_override = (
            "Open-OpenCode-Isolated.cmd" if is_windows_platform() else "Open-OpenCode-Isolated.sh"
        )
    launcher_path = prepare_opencode_launcher(
        config=config,
        profile=profile,
        working_directory_override=project_path,
        launcher_name_override=launcher_name_override,
    )
    existing_launchers = detect_opencode_launcher_instances(launcher_path)
    if existing_launchers:
        return _result(
            "ok",
            "open-opencode",
            "OpenCode launch je već u toku; sačekaj da se postojeći launcher završi.",
        )

    log_path = config.install_root / "logs" / "opencode-launch.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"Launching OpenCode via {launcher_path}\n")
    try:
        _launch_opencode_launcher(launcher_path)
    except RuntimeError as exc:
        return _result("error", "open-opencode", str(exc))

    return _result(
        "ok",
        "open-opencode",
        _build_opencode_open_summary(
            launch_mode=normalized_launch_mode,
            project_path=project_path,
            workspace_info=workspace_info,
            gui=False,
        ),
    )


def prepare_opencode_launcher(
    config: ControlCenterConfig | None = None,
    profile: str = "",
    working_directory_override: Path | None = None,
    launcher_name_override: str | None = None,
    platform: str | None = None,
) -> Path:
    config = config or get_config()
    executable_path = _resolve_opencode_executable_path(config)
    managed_config_path = config.install_root / "config" / "opencode" / "managed-config.json"
    settings = load_effective_settings_state(config)
    if not executable_path.is_file():
        raise FileNotFoundError(f"OpenCode executable nije pronađen: {executable_path}")
    if not managed_config_path.is_file():
        raise FileNotFoundError(
            f"OpenCode managed config nije pronađen: {managed_config_path}"
        )

    env = _build_opencode_launch_environment(
        managed_config_path=managed_config_path,
        settings=settings,
        profile=profile,
    )
    working_directory = (
        Path(working_directory_override).expanduser().resolve()
        if working_directory_override is not None
        else _resolve_opencode_working_directory(settings=settings, config=config)
    )
    launcher_name = launcher_name_override or (
        "Open-OpenCode.cmd" if is_windows_platform(platform) else "Open-OpenCode.sh"
    )
    launcher_path = config.install_root / "control-center" / launcher_name
    launcher_path.parent.mkdir(parents=True, exist_ok=True)
    _write_opencode_launcher(
        launcher_path=launcher_path,
        executable_path=executable_path,
        working_directory=working_directory,
        env=env,
        platform=platform,
    )
    return launcher_path


def _normalize_opencode_launch_mode(value: str) -> str:
    candidate = str(value or "").strip().lower()
    if candidate == "isolated":
        return "isolated"
    return "direct"


def _resolve_opencode_working_directory(
    *,
    settings: dict[str, object],
    config: ControlCenterConfig,
) -> Path:
    working_directory = Path(str(settings.get("workingDirectory") or config.install_root)).expanduser()
    if working_directory.exists() and not working_directory.is_dir():
        raise RuntimeError(f"Radni direktorijum nije folder: {working_directory}")
    working_directory.mkdir(parents=True, exist_ok=True)
    return working_directory.resolve()


def _prepare_isolated_opencode_workspace(
    *,
    config: ControlCenterConfig,
    working_directory: Path,
) -> dict[str, object]:
    from local_ai_control_center_installer.control_center_backend.services.tuning_lab_service import (
        _build_tuning_workspace_copy_ignore,
        _git_repo_is_clean,
        _git_repo_root,
        _path_is_relative_to,
    )

    workspace_root = config.install_root / "workspaces" / "opencode"
    workspace_root.mkdir(parents=True, exist_ok=True)
    source_dir = Path(working_directory).resolve()
    if (
        source_dir == config.install_root
        or _path_is_relative_to(source_dir, config.control_center_config_root)
        or _path_is_relative_to(source_dir, workspace_root)
    ):
        scratch_root = Path(tempfile.mkdtemp(prefix="gui-scratch-", dir=str(workspace_root)))
        _seed_opencode_scratch_workspace(scratch_root=scratch_root, source_dir=source_dir)
        return {
            "mode": "scratch",
            "workspacePath": str(scratch_root),
            "workspaceRoot": str(scratch_root),
            "cleanupPath": str(scratch_root),
            "sourceRoot": str(source_dir),
        }
    repo_root = _git_repo_root(source_dir)
    if repo_root is not None and _git_repo_is_clean(repo_root):
        reserved_path = Path(tempfile.mkdtemp(prefix="gui-worktree-", dir=str(workspace_root)))
        shutil.rmtree(reserved_path, ignore_errors=True)
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(reserved_path), "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        relative_subdir = source_dir.relative_to(repo_root) if source_dir != repo_root else Path(".")
        effective_workspace = reserved_path / relative_subdir if str(relative_subdir) != "." else reserved_path
        return {
            "mode": "git-worktree",
            "workspacePath": str(effective_workspace),
            "workspaceRoot": str(reserved_path),
            "cleanupPath": str(reserved_path),
            "sourceRoot": str(repo_root),
        }

    copy_root = Path(tempfile.mkdtemp(prefix="gui-copy-", dir=str(workspace_root)))
    shutil.rmtree(copy_root, ignore_errors=True)
    shutil.copytree(
        source_dir,
        copy_root,
        dirs_exist_ok=False,
        ignore=_build_tuning_workspace_copy_ignore(source_dir=source_dir, config=config),
    )
    return {
        "mode": "copy",
        "workspacePath": str(copy_root),
        "workspaceRoot": str(copy_root),
        "cleanupPath": str(copy_root),
        "sourceRoot": str(source_dir),
    }


def _resolve_opencode_workspace_root(config: ControlCenterConfig) -> Path:
    return config.install_root / "workspaces" / "opencode"


def _collect_active_opencode_workspace_paths(
    *,
    workspace_root: Path,
    instances: list[dict[str, object]],
) -> set[Path]:
    active_paths: set[Path] = set()
    for instance in instances:
        if not isinstance(instance, dict):
            continue
        command_line = str(instance.get("commandLine") or instance.get("CommandLine") or "")
        for candidate_path in _extract_workspace_paths_from_command_line(
            command_line=command_line,
            workspace_root=workspace_root,
        ):
            active_paths.add(candidate_path)
    return active_paths


def _extract_workspace_paths_from_command_line(
    *,
    command_line: str,
    workspace_root: Path,
) -> list[Path]:
    if not command_line.strip():
        return []
    matches = re.findall(r'"([^"]+)"|(\S+)', command_line)
    candidates: list[Path] = []
    for quoted, bare in matches:
        raw_value = (quoted or bare or "").strip().strip('"')
        if not raw_value:
            continue
        workspace_path = _resolve_opencode_workspace_candidate(Path(raw_value), workspace_root)
        if workspace_path is None or workspace_path in candidates:
            continue
        candidates.append(workspace_path)
    return candidates


def _resolve_opencode_workspace_candidate(candidate: Path, workspace_root: Path) -> Path | None:
    candidate_resolved = candidate.expanduser().resolve(strict=False)
    workspace_root_resolved = workspace_root.resolve(strict=False)
    try:
        relative = candidate_resolved.relative_to(workspace_root_resolved)
    except ValueError:
        return None
    if not relative.parts:
        return None
    return workspace_root_resolved / relative.parts[0]


def _scan_opencode_disposable_workspaces(
    *,
    workspace_root: Path,
    active_paths: set[Path],
    protect_most_recent: bool,
) -> list[dict[str, object]]:
    if not workspace_root.exists():
        return []
    disposable_entries: list[tuple[Path, str, os.stat_result, int]] = []
    for entry in workspace_root.iterdir():
        if not entry.is_dir():
            continue
        workspace_kind = _classify_opencode_disposable_workspace(entry.name)
        if workspace_kind is None:
            continue
        try:
            stat_result = entry.stat()
        except OSError:
            continue
        size_bytes = _measure_directory_size(entry)
        disposable_entries.append((entry.resolve(strict=False), workspace_kind, stat_result, size_bytes))

    fallback_protected_path: Path | None = None
    if protect_most_recent and disposable_entries:
        fallback_protected_path = max(disposable_entries, key=lambda item: item[2].st_mtime)[0]

    items: list[dict[str, object]] = []
    for entry_path, workspace_kind, stat_result, size_bytes in sorted(
        disposable_entries,
        key=lambda item: (item[0] not in active_paths, -(item[2].st_mtime)),
    ):
        is_active = entry_path in active_paths
        is_recent_fallback_protected = bool(
            fallback_protected_path is not None and entry_path == fallback_protected_path and not is_active
        )
        items.append(
            {
                "name": entry_path.name,
                "path": str(entry_path),
                "kind": workspace_kind,
                "sizeBytes": size_bytes,
                "sizeLabel": _format_storage_size(size_bytes),
                "modifiedAt": stat_result.st_mtime,
                "isDisposable": True,
                "isActive": is_active,
                "isRecentFallbackProtected": is_recent_fallback_protected,
                "cleanupEligible": not is_active and not is_recent_fallback_protected,
            }
        )
    return items


def _classify_opencode_disposable_workspace(name: str) -> str | None:
    for prefix, label in OPENCODE_DISPOSABLE_WORKSPACE_PREFIXES.items():
        if name.startswith(prefix):
            return label
    return None


def _measure_directory_size(root: Path) -> int:
    total = 0
    pending = [root]
    while pending:
        current = pending.pop()
        try:
            with os.scandir(current) as iterator:
                for entry in iterator:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            pending.append(Path(entry.path))
                            continue
                        total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def _is_opencode_workspace_cleanup_target(candidate_path: Path, workspace_root: Path) -> bool:
    candidate_resolved = candidate_path.resolve(strict=False)
    workspace_root_resolved = workspace_root.resolve(strict=False)
    try:
        relative = candidate_resolved.relative_to(workspace_root_resolved)
    except ValueError:
        return False
    if len(relative.parts) != 1:
        return False
    return _classify_opencode_disposable_workspace(candidate_resolved.name) is not None


def _remove_tree(path: Path) -> None:
    def _on_error(function, target_path, exc_info):
        try:
            Path(target_path).chmod(stat.S_IWRITE)
        except OSError:
            pass
        function(target_path)

    shutil.rmtree(path, onerror=_on_error)


def _format_storage_size(value: int) -> str:
    normalized = max(int(value or 0), 0)
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    size = float(normalized)
    unit = units[0]
    for candidate in units:
        unit = candidate
        if size < 1024 or candidate == units[-1]:
            break
        size /= 1024
    if unit == "B":
        return f"{int(size)} {unit}"
    return f"{size:.2f} {unit}"


def _record_opencode_auto_cleanup_state(
    config: ControlCenterConfig,
    payload: dict[str, object],
) -> None:
    atomic_write_json(config.opencode_hygiene_state_path, payload)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _build_manual_storage_review_locations() -> list[dict[str, str]]:
    home = Path.home()
    candidates = [
        ("Hugging Face keš", home / ".cache" / "huggingface" / "hub"),
        ("Ollama modeli", home / ".ollama" / "models"),
        ("LocalQwenHome modeli", home / "LocalQwenHome" / "models"),
        (
            "Pinokio API keš i aplikacije",
            Path(home.anchor) / "pinokio" / "api" if home.anchor else Path(""),
        ),
    ]
    visible_items: list[dict[str, str]] = []
    for label, path in candidates:
        if not str(path).strip() or not path.exists():
            continue
        visible_items.append(
            {
                "label": label,
                "path": str(path),
                "summary": "RuntimePilot ovu lokaciju ne briše automatski; proveri je ručno kada prostor opet počne da nestaje.",
            }
        )
    return visible_items


def _seed_opencode_scratch_workspace(*, scratch_root: Path, source_dir: Path) -> None:
    scratch_root.mkdir(parents=True, exist_ok=True)
    readme_path = scratch_root / "README.md"
    readme_path.write_text(
        "\n".join(
            [
                "# RuntimePilot isolated OpenCode workspace",
                "",
                "Ovo je lagani scratch workspace za probni rad u OpenCode GUI-ju.",
                "Koristi ga kada trenutni working directory nije pravi projekat nego RuntimePilot install root.",
                "",
                f"Izvorni working directory: {source_dir}",
            ]
        ),
        encoding="utf-8",
    )
    (scratch_root / ".gitignore").write_text(".codex/\nnode_modules/\n__pycache__/\n", encoding="utf-8")


def _build_opencode_open_summary(
    *,
    launch_mode: str,
    project_path: Path,
    workspace_info: dict[str, object] | None,
    gui: bool,
) -> str:
    if launch_mode == "isolated" and workspace_info is not None:
        workspace_mode = str(workspace_info.get("mode"))
        if workspace_mode == "git-worktree":
            mode_label = "git worktree"
        elif workspace_mode == "scratch":
            mode_label = "scratch workspace"
        else:
            mode_label = "kopija"
        if gui:
            return f"OpenCode GUI je pokrenut u izolovanom workspace-u ({mode_label}) na putanji: {project_path}"
        return (
            f"GUI nije dostupan; OpenCode je pokrenut kao CLI sesija u izolovanom workspace-u "
            f"({mode_label}) na putanji: {project_path}"
        )
    if gui:
        return f"OpenCode GUI je pokrenut nad radnim direktorijumom: {project_path}"
    return (
        f"GUI nije dostupan; OpenCode je pokrenut kao CLI sesija u terminalu nad radnim direktorijumom: "
        f"{project_path}"
    )


def detect_opencode_instances(executable_path: Path) -> list[dict[str, object]]:
    if not executable_path:
        return []
    executable_token = _normalize_windows_path_token(str(executable_path))
    if not executable_token:
        return []
    payloads = _query_opencode_processes()
    if not payloads:
        return []
    instances: list[dict[str, object]] = []
    for item in payloads:
        if not isinstance(item, dict):
            continue
        pid = item.get("pid") or item.get("ProcessId")
        if not isinstance(pid, int):
            continue
        command_line = str(item.get("commandLine") or item.get("CommandLine") or "")
        if not _command_line_matches_executable(command_line, executable_token):
            continue
        instances.append(
            {
                "pid": pid,
                "name": str(item.get("name") or item.get("Name") or ""),
                "commandLine": command_line,
            }
        )
    return instances


def detect_opencode_desktop_instances(executable_path: Path | None) -> list[dict[str, object]]:
    if not is_windows_platform() or executable_path is None:
        return []
    executable_token = _normalize_windows_path_token(str(executable_path))
    if not executable_token:
        return []
    payloads = _query_opencode_desktop_processes()
    if not payloads:
        return []
    instances: list[dict[str, object]] = []
    for item in payloads:
        if not isinstance(item, dict):
            continue
        pid = item.get("pid") or item.get("ProcessId")
        if not isinstance(pid, int):
            continue
        command_line = str(item.get("commandLine") or item.get("CommandLine") or "")
        if not _command_line_matches_executable(command_line, executable_token):
            continue
        instances.append(
            {
                "pid": pid,
                "name": str(item.get("name") or item.get("Name") or ""),
                "commandLine": command_line,
            }
        )
    return instances


def detect_opencode_launcher_instances(launcher_path: Path) -> list[dict[str, object]]:
    if not is_windows_platform():
        return []
    launcher_token = _normalize_windows_path_token(str(launcher_path))
    if not launcher_token:
        return []
    payloads = _query_shell_launcher_processes()
    if not payloads:
        return []
    instances: list[dict[str, object]] = []
    for item in payloads:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("Name") or "").strip().lower()
        if name not in {"cmd.exe", "wt.exe"}:
            continue
        pid = item.get("pid") or item.get("ProcessId")
        if not isinstance(pid, int):
            continue
        command_line = str(item.get("commandLine") or item.get("CommandLine") or "")
        if not _command_line_matches_executable(command_line, launcher_token):
            continue
        instances.append(
            {
                "pid": pid,
                "name": name,
                "commandLine": command_line,
            }
        )
    return instances


def _query_opencode_processes() -> list[dict[str, object]]:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            (
                "$matches = Get-CimInstance Win32_Process "
                "-Filter \"Name = 'opencode.exe'\" "
                "| Select-Object ProcessId, Name, CommandLine; "
                "$matches | ConvertTo-Json -Compress -Depth 3"
            ),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return []
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else [parsed]


def _query_opencode_desktop_processes() -> list[dict[str, object]]:
    if not is_windows_platform():
        return []
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            (
                "$matches = Get-CimInstance Win32_Process "
                "-Filter \"Name = 'OpenCode.exe'\" "
                "| Select-Object ProcessId, Name, CommandLine; "
                "$matches | ConvertTo-Json -Compress -Depth 3"
            ),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return []
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else [parsed]


def _query_shell_launcher_processes() -> list[dict[str, object]]:
    if not is_windows_platform():
        return []
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            (
                "$matches = Get-CimInstance Win32_Process "
                "| Where-Object { $_.Name -in @('cmd.exe', 'wt.exe') } "
                "| Select-Object ProcessId, Name, CommandLine; "
                "$matches | ConvertTo-Json -Compress -Depth 3"
            ),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return []
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else [parsed]


def _normalize_windows_path_token(value: str) -> str:
    return value.replace("/", "\\").strip().strip('"').lower()


def _command_line_matches_executable(command_line: str, executable_token: str) -> bool:
    if not command_line or not executable_token:
        return False
    normalized_command = _normalize_windows_path_token(command_line)
    return executable_token in normalized_command


def _resolve_opencode_executable_path(config: ControlCenterConfig) -> Path:
    manifest = load_opencode_manifest()
    artifact = manifest["opencode_artifact"]
    launch = artifact["launch"]["executable_relative_path"]
    return config.install_root / artifact["install_subdir"] / launch


def _find_existing_file_with_exact_name(candidate: Path) -> Path | None:
    candidate_name = candidate.name
    if not candidate_name:
        return None
    try:
        if not candidate.parent.is_dir():
            return None
        for entry in os.scandir(candidate.parent):
            if entry.name != candidate_name:
                continue
            if not entry.is_file():
                continue
            return Path(entry.path)
    except OSError:
        return None
    return None


def _resolve_windows_opencode_desktop_executable_path(
    config: ControlCenterConfig,
) -> Path | None:
    if not is_windows_platform():
        return None
    cli_executable_path = _resolve_opencode_executable_path(config)
    candidates = [
        config.install_root / "tools" / "opencode" / "OpenCode.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "opencode" / "OpenCode.exe",
        Path(os.environ.get("ProgramFiles", "")) / "OpenCode" / "OpenCode.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "OpenCode" / "OpenCode.exe",
    ]
    for candidate in candidates:
        if not str(candidate).strip():
            continue
        matched = _find_existing_file_with_exact_name(candidate)
        if matched is None:
            continue
        try:
            if matched.samefile(cli_executable_path):
                continue
        except OSError:
            pass
        return matched
    return None


def _build_opencode_launch_environment(
    *,
    managed_config_path: Path,
    settings: dict[str, object],
    profile: str,
) -> dict[str, str]:
    env = os.environ.copy()
    env["OPENCODE_CONFIG"] = str(managed_config_path)
    env["LACC_PROFILE"] = profile or str(settings["profile"])
    env["LACC_OPENCODE_SECURITY_MODE"] = str(settings["securityMode"])
    env["LACC_OPENCODE_CAPABILITY_MODE"] = str(settings["capabilityMode"])
    env["LACC_OPENCODE_BUILD_STEPS"] = str(settings["buildSteps"])
    env["LACC_OPENCODE_PLAN_STEPS"] = str(settings["planSteps"])
    env["LACC_OPENCODE_GENERAL_STEPS"] = str(settings["generalSteps"])
    env["LACC_OPENCODE_EXPLORE_STEPS"] = str(settings["exploreSteps"])
    return env


def _write_opencode_launcher(
    *,
    launcher_path: Path,
    executable_path: Path,
    working_directory: Path,
    env: dict[str, str],
    platform: str | None = None,
) -> None:
    if not is_windows_platform(platform):
        lines = [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            f'cd {shlex.quote(str(working_directory))}',
        ]
        for key in [
            "OPENCODE_CONFIG",
            "LACC_PROFILE",
            "LACC_OPENCODE_SECURITY_MODE",
            "LACC_OPENCODE_CAPABILITY_MODE",
            "LACC_OPENCODE_BUILD_STEPS",
            "LACC_OPENCODE_PLAN_STEPS",
            "LACC_OPENCODE_GENERAL_STEPS",
            "LACC_OPENCODE_EXPLORE_STEPS",
        ]:
            value = str(env.get(key, ""))
            lines.append(f'export {key}="{value}"')
        lines.append(f'exec "{executable_path}" "$@"')
        launcher_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        _ensure_executable_bit(launcher_path)
        return

    lines = [
        "@echo off",
        "setlocal",
        *_build_windows_opencode_launcher_guard_lines(
            launcher_path=launcher_path,
            executable_path=executable_path,
        ),
        "title RuntimePilot - OpenCode",
        f'cd /d "{working_directory}"',
    ]
    for key in [
        "OPENCODE_CONFIG",
        "LACC_PROFILE",
        "LACC_OPENCODE_SECURITY_MODE",
        "LACC_OPENCODE_CAPABILITY_MODE",
        "LACC_OPENCODE_BUILD_STEPS",
        "LACC_OPENCODE_PLAN_STEPS",
        "LACC_OPENCODE_GENERAL_STEPS",
        "LACC_OPENCODE_EXPLORE_STEPS",
    ]:
        value = str(env.get(key, ""))
        escaped_value = value.replace('"', '""')
        lines.append(f'set "{key}={escaped_value}"')
    lines.append(f'"{executable_path}"')
    lines.append('set "OPENCODE_EXIT_CODE=%ERRORLEVEL%"')
    lines.append("if not \"%OPENCODE_EXIT_CODE%\"==\"0\" (")
    lines.append("  echo.")
    lines.append("  echo OpenCode je završio sa kodom %OPENCODE_EXIT_CODE%.")
    lines.append("  echo Proveri model, konfiguraciju i logove ako se prozor odmah zatvorio.")
    lines.append("  pause")
    lines.append(")")
    lines.append("endlocal")
    launcher_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")


def _build_windows_opencode_launcher_guard_lines(
    *,
    launcher_path: Path,
    executable_path: Path,
) -> list[str]:
    launcher_token = _quote_powershell_string(str(launcher_path))
    executable_token = _quote_powershell_string(str(executable_path))
    powershell_script = (
        f"$launcherPath = {launcher_token}; "
        f"$executablePath = {executable_token}; "
        "$launcherMatches = Get-CimInstance Win32_Process "
        "| Where-Object { $_.Name -eq 'cmd.exe' -and $_.CommandLine -like ('*' + $launcherPath + '*') }; "
        "$runtimeMatches = Get-CimInstance Win32_Process "
        "| Where-Object { $_.Name -eq 'opencode.exe' -and $_.CommandLine -like ('*' + $executablePath + '*') }; "
        "if (($runtimeMatches | Measure-Object).Count -gt 0 -or ($launcherMatches | Measure-Object).Count -gt 1) { exit 0 }; "
        "exit 1"
    )
    return [
        f'powershell -NoProfile -ExecutionPolicy Bypass -Command "{powershell_script}" >nul 2>nul',
        'if "%ERRORLEVEL%"=="0" (',
        "  echo OpenCode launch je već u toku ili je sesija već otvorena.",
        "  endlocal",
        "  exit /b 0",
        ")",
    ]


def _build_opencode_launch_preview(
    *,
    config: ControlCenterConfig,
    executable_path: Path,
    desktop_executable_path: Path | None,
    managed_config_path: Path,
    settings: dict[str, object],
) -> dict[str, object]:
    launcher_name = "Open-OpenCode.cmd" if is_windows_platform() else "Open-OpenCode.sh"
    launcher_path = config.install_root / "control-center" / launcher_name
    env = _build_opencode_launch_environment(
        managed_config_path=managed_config_path,
        settings=settings,
        profile="",
    )
    env_items = [
        {"key": key, "value": str(env.get(key, ""))}
        for key in [
            "OPENCODE_CONFIG",
            "LACC_PROFILE",
            "LACC_OPENCODE_SECURITY_MODE",
            "LACC_OPENCODE_CAPABILITY_MODE",
            "LACC_OPENCODE_BUILD_STEPS",
            "LACC_OPENCODE_PLAN_STEPS",
            "LACC_OPENCODE_GENERAL_STEPS",
            "LACC_OPENCODE_EXPLORE_STEPS",
        ]
    ]
    if not is_windows_platform():
        shell_command = f'bash "{launcher_path}"'
        powershell_command = "\n".join(
            [
                f'cd "{settings["workingDirectory"]}"',
                *(f'export {item["key"]}="{item["value"]}"' for item in env_items),
                f'"{executable_path}"',
            ]
        )
        return {
            "shellLabel": "Shell",
            "launcherPath": str(launcher_path),
            "launcherCommand": shell_command,
            "powershellCommand": powershell_command,
            "workingDirectory": str(settings["workingDirectory"]),
            "environment": env_items,
            "managedConfig": _build_managed_opencode_config_preview(managed_config_path),
            "generationSummary": _build_generation_defaults_summary(settings),
            "summary": (
                "OpenCode koristi managed config, a local-lacc inference podrazumevana sampling "
                "podešavanja dobija kroz runtime proxy sloj iz RuntimePilot-a."
            ),
        }

    if desktop_executable_path and desktop_executable_path.is_file():
        powershell_lines = [
            f'Set-Location "{settings["workingDirectory"]}"',
            *(
                f'$env:{item["key"]} = "{_escape_powershell_value(str(item["value"]))}"'
                for item in env_items
            ),
            f'Start-Process -FilePath "{desktop_executable_path}"',
        ]
        return {
            "shellLabel": "Desktop",
            "launcherPath": str(desktop_executable_path),
            "launcherCommand": str(desktop_executable_path),
            "powershellCommand": "\n".join(powershell_lines),
            "workingDirectory": str(settings["workingDirectory"]),
            "environment": env_items,
            "managedConfig": _build_managed_opencode_config_preview(managed_config_path),
            "generationSummary": _build_generation_defaults_summary(settings),
            "summary": (
                "OpenCode GUI se otvara sa RuntimePilot managed config podešavanjima, "
                "dok CLI fallback ostaje dostupan ako desktop aplikacija nije instalirana."
            ),
        }

    powershell_lines = [
        f'Set-Location "{settings["workingDirectory"]}"',
        *(
            f'$env:{item["key"]} = "{_escape_powershell_value(str(item["value"]))}"'
            for item in env_items
        ),
        f'& "{executable_path}"',
    ]
    launch_command, preview_command = _build_windows_opencode_terminal_command(launcher_path)
    return {
        "shellLabel": "PowerShell",
        "launcherPath": str(launcher_path),
        "launcherCommand": preview_command,
        "powershellCommand": "\n".join(powershell_lines),
        "workingDirectory": str(settings["workingDirectory"]),
        "environment": env_items,
        "managedConfig": _build_managed_opencode_config_preview(managed_config_path),
        "generationSummary": _build_generation_defaults_summary(settings),
        "summary": (
            "OpenCode model i provider dolaze iz managed-config.json, a local-lacc u sebi koristi "
            "trenutni runtime, aktivni model i sampling podrazumevana podešavanja iz RuntimePilot-a."
        ),
    }


def _launch_opencode_launcher(launcher_path: Path) -> None:
    if not is_windows_platform():
        terminal_command = _build_linux_terminal_command(launcher_path)
        if terminal_command is None:
            raise RuntimeError(
                "Linux OpenCode launcher zahteva podržan terminal emulator (npr. x-terminal-emulator ili gnome-terminal)."
            )
        subprocess.Popen(
            terminal_command,
            cwd=str(launcher_path.parent),
            close_fds=False,
        )
        return

    command, _preview = _build_windows_opencode_terminal_command(launcher_path)
    popen_kwargs: dict[str, object] = {"cwd": str(launcher_path.parent)}
    if command and Path(command[0]).name.lower() == "cmd.exe":
        popen_kwargs["creationflags"] = new_console_subprocess_creationflags()
    subprocess.Popen(command, **popen_kwargs)


def _launch_opencode_desktop(
    *,
    desktop_executable_path: Path,
    working_directory: Path,
    project_path: Path,
    env: dict[str, str],
) -> None:
    subprocess.Popen(
        [str(desktop_executable_path), str(project_path)],
        cwd=str(working_directory),
        env=env,
    )


def _build_windows_opencode_terminal_command(launcher_path: Path) -> tuple[list[str], str]:
    windows_terminal_path = shutil.which("wt.exe") or shutil.which("wt")
    if windows_terminal_path:
        command = [
            windows_terminal_path,
            "new-tab",
            "--title",
            "RuntimePilot - OpenCode",
            "cmd.exe",
            "/d",
            "/c",
            str(launcher_path),
        ]
        return command, f'wt.exe new-tab --title "RuntimePilot - OpenCode" cmd.exe /d /c "{launcher_path}"'
    command = ["cmd.exe", "/d", "/c", str(launcher_path)]
    return command, f'cmd.exe /d /c "{launcher_path}"'


def _build_managed_opencode_config_preview(managed_config_path: Path) -> dict[str, object]:
    fallback = {
        "model": "",
        "selectedProvider": "",
        "localProviderBaseUrl": "",
        "enabledProviders": [],
    }
    if not managed_config_path.is_file():
        return fallback
    try:
        payload = json.loads(managed_config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback
    if not isinstance(payload, dict):
        return fallback

    model = str(payload.get("model", "") or "")
    selected_provider = model.split("/", 1)[0] if "/" in model else ""
    provider_root = payload.get("provider")
    if not isinstance(provider_root, dict):
        provider_root = payload.get("providers")
    if not isinstance(provider_root, dict):
        provider_root = {}

    enabled_providers = payload.get("enabled_providers")
    if isinstance(enabled_providers, list):
        enabled_provider_list = [str(item) for item in enabled_providers if str(item).strip()]
    else:
        enabled_provider_list = [str(key) for key in provider_root.keys() if str(key).strip()]

    provider_id = selected_provider or "local-lacc"
    provider_entry = provider_root.get(provider_id)
    if not isinstance(provider_entry, dict):
        provider_entry = provider_root.get("local-lacc")

    base_url = ""
    if isinstance(provider_entry, dict):
        options = provider_entry.get("options")
        if isinstance(options, dict):
            base_url = str(options.get("baseURL", "") or options.get("baseUrl", "") or "")

    return {
        "model": model,
        "selectedProvider": selected_provider,
        "localProviderBaseUrl": base_url,
        "enabledProviders": enabled_provider_list,
    }


def _build_linux_terminal_command(launcher_path: Path) -> list[str] | None:
    launcher = str(launcher_path)
    terminal_candidates = [
        ["x-terminal-emulator", "-e", launcher],
        ["gnome-terminal", "--", launcher],
        ["konsole", "-e", launcher],
        ["xfce4-terminal", "--command", launcher],
        ["xterm", "-e", launcher],
    ]
    for candidate in terminal_candidates:
        if shutil.which(candidate[0]):
            return candidate
    return None


def _escape_powershell_value(value: str) -> str:
    return value.replace('"', '`"')


def _quote_powershell_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _ensure_executable_bit(path: Path) -> None:
    current_mode = path.stat().st_mode
    path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def load_opencode_step_schema_payload(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    return load_opencode_step_schema(config)


def save_opencode_settings_payload(
    payload: dict[str, object],
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    return apply_opencode_settings(payload, config)


def save_opencode_step_preset_payload(
    payload: dict[str, object],
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    return save_opencode_step_preset(payload, config)


def delete_opencode_step_preset_payload(
    preset_id: str,
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    return delete_opencode_step_preset(preset_id, config)


def _result(status: str, action: str, summary: str) -> dict[str, object]:
    return {
        "status": status,
        "action": action,
        "summary": summary,
        "details": {
            "returncode": 0 if status == "ok" else 1,
            "stdout": summary if status == "ok" else "",
            "stderr": "" if status == "ok" else summary,
        },
    }


def _build_opencode_bootstrap_download_plan() -> DownloadPlan:
    try:
        manifest = load_opencode_manifest()
    except (OSError, ValueError):
        return DownloadPlan(items=())

    artifact = manifest["opencode_artifact"]
    size_bytes = artifact.get("size_bytes")
    normalized_size = size_bytes if isinstance(size_bytes, int) else None
    return DownloadPlan(
        items=(
            DownloadPlanItem(
                key=OPENCODE_ARTIFACT_DOWNLOAD_KEY,
                label="OpenCode",
                url=str(artifact["url"]),
                destination_hint=str(artifact["install_subdir"]),
                size_bytes=normalized_size,
                queue_index=1,
                queue_total=1,
            ),
        )
    )


def _security_mode_label(value: str) -> str:
    return {
        "strict": "Strogo ograničen agent",
        "workspace-write": "Ograničen agent sa blacklist pravilima",
        "open": "Potpuno otvoren agent",
    }.get(value, value)


def _capability_mode_label(value: str) -> str:
    return {
        "read-only": "1. Samo čitanje fajlova",
        "read-write": "2. Čitanje + izmena fajlova",
        "confirm-commands": "3. Čitanje + izmena + komande uz potvrdu",
        "auto-commands": "4. Čitanje + izmena + komande bez potvrde",
    }.get(value, value)


def _build_local_provider_search_summary(settings: dict[str, object]) -> str:
    mode = str(settings.get("webSearchMode", "off") or "off")
    prefix = str(settings.get("webSearchPromptPrefix", "/web") or "/web")
    if mode == "always":
        return "Local-lacc provider uvek prolazi kroz lokalni SearxNG search augmentation sloj."
    if mode == "on-demand":
        return (
            "Local-lacc provider koristi lokalni SearxNG search sloj samo kada prompt "
            f"krene prefiksom {prefix}."
        )
    return "Local-lacc provider trenutno radi bez automatskog web search augmentation-a."


def _build_generation_defaults_summary(settings: dict[str, object]) -> str:
    return (
        f"temp {settings.get('temperature', 0.8)} | top-k {settings.get('topK', 40)} | "
        f"top-p {settings.get('topP', 0.95)} | min-p {settings.get('minP', 0.05)} | "
        f"repeat {settings.get('repeatPenalty', 1.0)} / last-n {settings.get('repeatLastN', 64)} | "
        f"presence {settings.get('presencePenalty', 0.0)} | "
        f"frequency {settings.get('frequencyPenalty', 0.0)} | seed {settings.get('seed', -1)}"
    )


def _build_session_state(
    *,
    has_instances: bool,
    has_desktop_instances: bool,
    launch_in_progress: bool,
    runtime_connected: bool,
    runtime_reason: str,
) -> tuple[str, str]:
    if has_desktop_instances and runtime_connected:
        return "connected", "OpenCode prozor je otvoren i povezan sa runtime-om."
    if has_desktop_instances:
        reason = runtime_reason or "Runtime trenutno nije pokrenut."
        return "app-only", f"OpenCode prozor je otvoren, ali backend nije spreman. {reason}"
    if has_instances and runtime_connected:
        return "connected", "OpenCode CLI sesija je otvorena u terminalu i povezana sa runtime-om."
    if has_instances:
        reason = runtime_reason or "Runtime trenutno nije pokrenut."
        return "app-only", f"OpenCode CLI sesija je otvorena u terminalu, ali backend nije spreman. {reason}"
    if launch_in_progress:
        return "launching", "OpenCode CLI launch je u toku i čeka se da se terminal sesija stabilizuje."
    if runtime_connected:
        return "runtime-ready", "Runtime je spreman za novi OpenCode session."
    reason = runtime_reason or "Runtime trenutno nije pokrenut."
    return "idle", f"OpenCode je dostupan, ali backend još nije spreman. {reason}"


def _build_open_action_contract(
    *,
    available: bool,
    config_exists: bool,
    session_state: str,
) -> tuple[str, str]:
    if not available:
        return "OpenCode nije instaliran", "OpenCode executable nije pronađen."
    if not config_exists:
        return "OpenCode config nedostaje", "OpenCode managed config nije pronađen."
    if session_state == "app-only":
        return "Pripremi backend za postojeći OpenCode", ""
    if session_state == "connected":
        return "OpenCode je već otvoren", ""
    return "Otvori OpenCode", ""


def _resolve_open_action_contract(
    *,
    available: bool,
    config_exists: bool,
    session_state: str,
) -> tuple[bool, str, str]:
    if not available:
        return False, "OpenCode nije instaliran", "OpenCode executable nije pronađen."
    if not config_exists:
        return False, "OpenCode config nedostaje", "OpenCode managed config nije pronađen."
    if session_state == "launching":
        return False, "OpenCode launch je u toku", "Sačekaj da se postojeći OpenCode launcher završi."
    if session_state == "app-only":
        return True, "Pripremi backend za postojeći OpenCode", ""
    if session_state == "connected":
        return True, "OpenCode je već otvoren", ""
    return True, "Otvori OpenCode", ""


def _build_bootstrap_action_contract(
    *,
    config: ControlCenterConfig,
    available: bool,
    config_exists: bool,
    runtime_state: dict[str, object],
) -> tuple[bool, str, str]:
    label = "Reinstall / popravi OpenCode" if available and config_exists else "Instaliraj OpenCode"
    active_model_id = str(runtime_state.get("active_model_id", "") or "").strip().lower()
    active_model_label = str(runtime_state.get("active_model", "") or "").strip().lower()
    active_model_path = Path(str(runtime_state.get("active_model_path", "") or ""))
    if (
        not active_model_path.is_file()
        or not active_model_id
        or active_model_id == "unknown"
        or active_model_label in {"", "unknown", "nema aktivnog modela"}
    ):
        return (
            False,
            label,
            "Aktivan model nije podešen. Aktiviraj lokalni model pre instalacije OpenCode-a.",
        )
    try:
        load_runtime_endpoint_config(config.runtime_endpoint_config_path)
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return (
            False,
            label,
            "Runtime endpoint konfiguracija nedostaje ili je neispravna. Pokreni ili aktiviraj runtime pre instalacije OpenCode-a.",
        )
    return True, label, ""
