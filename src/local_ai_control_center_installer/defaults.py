from dataclasses import dataclass, field
from pathlib import Path
import threading
import shutil
import subprocess
import sys
import tempfile
import inspect
import time

from local_ai_control_center_installer.apply_phase import apply_bootstrap_phase
from local_ai_control_center_installer.dependencies import (
    apply_dependency_decision,
    scan_all_dependencies,
)
from local_ai_control_center_installer.download_plan import build_download_plan
from local_ai_control_center_installer.downloads import download_file
from local_ai_control_center_installer.first_run_validation import (
    FIRST_RUN_SMOKE_TIMEOUT_SECONDS,
    apply_first_run_validation,
)
from local_ai_control_center_installer.product_gate import apply_product_gate
from local_ai_control_center_installer.prompts import collect_installer_answers
from local_ai_control_center_installer.reporting import (
    build_run_paths,
    persist_install_root_reports,
    write_human_log,
    write_json_report,
)
from local_ai_control_center_installer.opencode_bootstrap import (
    apply_opencode_bootstrap,
)
from local_ai_control_center_installer.opencode_verification import (
    OPENCODE_SMOKE_TIMEOUT_SECONDS,
    apply_opencode_verification,
)
from local_ai_control_center_installer.runtime_bootstrap import apply_runtime_payload
from local_ai_control_center_installer.server_verification import (
    apply_server_verification,
)
from local_ai_control_center_installer.session import InstallerSession
from local_ai_control_center_installer.control_center_runtime import (
    apply_control_center_integration,
)
from local_ai_control_center_installer.turboquant import apply_turboquant

INSTALL_PHASE_TOTAL_STEPS = 11
SILENT_PHASE_HEARTBEAT_INTERVAL_SECONDS = 15.0
HEARTBEAT_POLL_INTERVAL_SECONDS = 0.5
SERVER_VERIFICATION_EXPECTED_SECONDS = 30.0
CONTROL_CENTER_EXPECTED_SECONDS = 20.0


@dataclass
class InstallProgressTracker:
    start_monotonic: float
    total_steps: int = INSTALL_PHASE_TOTAL_STEPS
    completed_durations: list[float] = field(default_factory=list)
    active_step_index: int | None = None
    active_step_started_at: float | None = None
    active_step_expected_duration: float | None = None
    active_step_heartbeat_message: str | None = None
    last_output_monotonic: float | None = None
    state_lock: object = field(
        default_factory=threading.Lock,
        repr=False,
        compare=False,
    )


_install_progress_tracker: InstallProgressTracker | None = None


def default_collect_answers(session: InstallerSession) -> InstallerSession:
    return collect_installer_answers(session)


def default_scan_dependencies(session: InstallerSession) -> InstallerSession:
    _reset_install_progress_tracker()
    probes = {
        "python": _probe_python_version,
    }
    _print_phase_message(1, "Checking installation prerequisites...")
    session = scan_all_dependencies(
        session,
        probes=probes,
    )
    _attempt_missing_dependency_installs(
        session,
        probes=probes,
        install_strategies=_build_dependency_install_strategies(session.platform),
    )
    status = "ready" if all(
        dependency.status == "ready"
        for dependency in session.dependencies
        if dependency.required
    ) else "failed"
    _print_phase_message(1, f"Installation prerequisites status: {status}", complete=True)
    return session


def default_apply_phase(session: InstallerSession) -> InstallerSession:
    return _run_phase_with_status(
        session,
        step_index=2,
        start_message="Applying bootstrap decisions...",
        status_label="Bootstrap status",
        step_fn=lambda current_session: apply_bootstrap_phase(
            current_session, temp_root=_default_temp_root()
        ),
        status_getter=lambda current_session: current_session.bootstrap_status,
    )


def default_prepare_download_plan(session: InstallerSession) -> InstallerSession:
    if session.download_plan is not None:
        _print_phase_message(3, "Preparing download plan...")
        item_count = _count_download_plan_items(session.download_plan)
        if item_count is None:
            _print_phase_message(3, "Download plan already prepared.", complete=True)
        else:
            _print_phase_message(
                3,
                f"Download plan already prepared: {item_count} item(s).",
                complete=True,
            )
        return session

    if session.bootstrap_status != "ready":
        _print_phase_message(3, "Preparing download plan...")
        _print_phase_message(3, "Download plan skipped.", complete=True)
        return session
    _print_phase_message(3, "Preparing download plan...")
    try:
        session.download_plan = build_download_plan(session)
    except (OSError, ValueError):
        session.download_plan = None
    item_count = _count_download_plan_items(session.download_plan)
    if item_count is None:
        _print_phase_message(3, "Download plan unavailable.", complete=True)
    else:
        _print_phase_message(3, f"Download plan ready: {item_count} item(s).", complete=True)
    return session


def default_apply_runtime_payload(session: InstallerSession) -> InstallerSession:
    progress_callback = _build_download_progress_callback()
    return _run_phase_with_status(
        session,
        step_index=4,
        start_message="Checking local runtime payload...",
        status_label="Runtime payload status",
        step_fn=lambda current_session: apply_runtime_payload(
            current_session,
            temp_root=_default_temp_root(),
            download_runtime_archive=lambda url, destination, *, plan_item=None: download_file(
                url,
                destination,
                progress_callback=progress_callback,
                plan_item=plan_item,
            ),
            download_model_file=lambda url, destination, *, plan_item=None: download_file(
                url,
                destination,
                progress_callback=progress_callback,
                plan_item=plan_item,
            ),
        ),
        status_getter=lambda current_session: current_session.runtime_payload_status,
    )


def default_apply_server_verification(session: InstallerSession) -> InstallerSession:
    return _run_phase_with_status(
        session,
        step_index=5,
        start_message="Verifying local llama.cpp server...",
        status_label="llama.cpp server verification status",
        heartbeat_message="llama.cpp server verification is still running...",
        expected_duration_seconds=SERVER_VERIFICATION_EXPECTED_SECONDS,
        step_fn=lambda current_session: apply_server_verification(
            current_session,
            temp_root=_default_temp_root(),
        ),
        status_getter=lambda current_session: current_session.server_verification_status,
    )


def default_apply_opencode_bootstrap(session: InstallerSession) -> InstallerSession:
    progress_callback = _build_download_progress_callback()
    return _run_phase_with_status(
        session,
        step_index=6,
        start_message="Checking OpenCode artifact...",
        status_label="OpenCode artifact status",
        step_fn=lambda current_session: apply_opencode_bootstrap(
            current_session,
            temp_root=_default_temp_root(),
            download_archive=lambda url, destination, *, plan_item=None: download_file(
                url,
                destination,
                progress_callback=progress_callback,
                plan_item=plan_item,
            ),
        ),
        status_getter=lambda current_session: current_session.opencode_artifact_status,
    )


def default_apply_opencode_verification(session: InstallerSession) -> InstallerSession:
    return _run_phase_with_status(
        session,
        step_index=7,
        start_message="Verifying OpenCode live route...",
        status_label="OpenCode live-route verification status",
        heartbeat_message="OpenCode live-route verification is still running...",
        expected_duration_seconds=OPENCODE_SMOKE_TIMEOUT_SECONDS,
        step_fn=lambda current_session: apply_opencode_verification(
            current_session,
            temp_root=_default_temp_root(),
        ),
        status_getter=lambda current_session: current_session.opencode_verification_status,
    )


def default_apply_first_run_validation(session: InstallerSession) -> InstallerSession:
    return _run_phase_with_status(
        session,
        step_index=9,
        start_message="Running first-run OpenCode smoke...",
        status_label="First-run smoke status",
        heartbeat_message="First-run OpenCode smoke is still running...",
        expected_duration_seconds=FIRST_RUN_SMOKE_TIMEOUT_SECONDS,
        step_fn=lambda current_session: apply_first_run_validation(
            current_session,
            temp_root=_default_temp_root(),
        ),
        status_getter=lambda current_session: current_session.first_run_status,
    )


def default_apply_turboquant(session: InstallerSession) -> InstallerSession:
    progress_callback = _build_download_progress_callback()
    return _run_phase_with_status(
        session,
        step_index=8,
        start_message="Checking TurboQuant...",
        status_label="TurboQuant status",
        step_fn=lambda current_session: _invoke_step_with_optional_kwargs(
            apply_turboquant,
            current_session,
            temp_root=_default_temp_root(),
            download_archive=lambda url, destination, *, plan_item=None: download_file(
                url,
                destination,
                progress_callback=progress_callback,
                plan_item=plan_item,
            ),
        ),
        status_getter=lambda current_session: current_session.turboquant_status,
    )


def default_apply_product_gate(session: InstallerSession) -> InstallerSession:
    return _run_phase_with_status(
        session,
        step_index=11,
        start_message="Finalizing installation status...",
        status_label="Product installation status",
        step_fn=apply_product_gate,
        status_getter=lambda current_session: current_session.product_installation_status,
    )


def default_apply_control_center_integration(session: InstallerSession) -> InstallerSession:
    return _run_phase_with_status(
        session,
        step_index=10,
        start_message="Deploying and launching control panel...",
        status_label="Control panel launch status",
        heartbeat_message="Control panel deployment is still running...",
        expected_duration_seconds=CONTROL_CENTER_EXPECTED_SECONDS,
        step_fn=lambda current_session: apply_control_center_integration(
            current_session,
            frozen=bool(getattr(sys, "frozen", False)),
            frozen_executable=sys.executable,
        ),
        status_getter=lambda current_session: current_session.control_center_launch_status,
    )


def default_write_reports(session: InstallerSession) -> None:
    run_paths = build_run_paths(_default_temp_root(), _build_run_id(session))
    write_human_log(session, run_paths.log_path)
    write_json_report(session, run_paths.json_report_path)
    if session.bootstrap_status == "ready":
        try:
            persist_install_root_reports(session)
        except OSError as exc:
            session.error_message = str(exc)
            if session.runtime_payload_status == "ready":
                session.runtime_payload_status = "failed"
            session.product_installation_status = "failed"
            if session.failing_step is None:
                session.failing_step = "install-root-persistence"
            write_human_log(session, run_paths.log_path)
            write_json_report(session, run_paths.json_report_path)
    _print_final_outcome(session, run_paths)
    _clear_install_progress_tracker()


def _default_temp_root() -> Path:
    return Path(tempfile.gettempdir())


def _run_phase_with_status(
    session: InstallerSession,
    *,
    step_index: int,
    start_message: str,
    status_label: str,
    heartbeat_message: str | None = None,
    expected_duration_seconds: float | None = None,
    heartbeat_interval_seconds: float = SILENT_PHASE_HEARTBEAT_INTERVAL_SECONDS,
    step_fn,
    status_getter,
) -> InstallerSession:
    _print_phase_message(
        step_index,
        start_message,
        expected_duration_seconds=expected_duration_seconds,
        heartbeat_message=heartbeat_message,
    )
    heartbeat_stop_event = threading.Event()
    heartbeat_thread = _start_phase_heartbeat_thread(
        step_index,
        stop_event=heartbeat_stop_event,
        heartbeat_interval_seconds=heartbeat_interval_seconds,
    )
    try:
        session = step_fn(session)
    finally:
        heartbeat_stop_event.set()
        heartbeat_thread.join(timeout=2.0)
    _print_phase_message(
        step_index,
        f"{status_label}: {status_getter(session)}",
        complete=True,
    )
    return session


def _invoke_step_with_optional_kwargs(step_fn, session: InstallerSession, **kwargs):
    parameters = inspect.signature(step_fn).parameters.values()
    if any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters):
        return step_fn(session, **kwargs)

    accepted_kwargs = {
        key: value for key, value in kwargs.items() if key in inspect.signature(step_fn).parameters
    }
    if accepted_kwargs:
        return step_fn(session, **accepted_kwargs)
    return step_fn(session)


def _count_download_plan_items(download_plan) -> int | None:
    if download_plan is None:
        return None
    if hasattr(download_plan, "items"):
        try:
            return len(download_plan.items)
        except TypeError:
            return None
    if isinstance(download_plan, dict):
        items = download_plan.get("items")
        if isinstance(items, list):
            return len(items)
    return None


def _build_run_id(session: InstallerSession) -> str:
    if session.started_at:
        return session.started_at.replace(":", "-")
    return "manual-run"


def _attempt_missing_dependency_installs(
    session: InstallerSession,
    *,
    probes: dict[str, callable],
    install_strategies: dict[str, callable],
) -> None:
    for record in session.dependencies:
        detected_version = record.version or ""
        if record.status == "ready":
            print(f"Dependency ready: {record.name} ({detected_version})")
            continue
        if not record.required or record.status != "missing-installable":
            print(f"Dependency status: {record.name} ({record.status})")
            continue

        print(f"Missing dependency detected: {record.name}")
        print(f"Attempting automatic install: {record.name}")
        strategy = install_strategies.get(record.name)
        if strategy is None:
            print(f"Automatic install failed: {record.name} (no packaged strategy)")
            apply_dependency_decision(
                record,
                user_accepts_install=True,
                install_fn=lambda dependency: False,
            )
            continue

        def install_and_verify(_dependency) -> bool:
            if not strategy():
                return False
            installed_version = probes[record.name]()
            if not installed_version:
                return False
            record.version = installed_version
            return True

        apply_dependency_decision(
            record,
            user_accepts_install=True,
            install_fn=install_and_verify,
        )

        if record.status == "ready":
            print(f"Automatic install succeeded: {record.name} ({record.version})")
        else:
            print(f"Automatic install failed: {record.name}")


def _build_dependency_install_strategies(
    platform: str | None = None,
) -> dict[str, callable]:
    if (platform or "").strip().lower() == "linux":
        return {}
    return {
        "git": _install_git_dependency,
        "node": _install_node_dependency,
        "build-tools": _install_build_tools_dependency,
    }


def _install_git_dependency() -> bool:
    return _install_with_winget("Git.Git")


def _install_node_dependency() -> bool:
    return _install_with_winget("OpenJS.NodeJS.LTS")


def _install_build_tools_dependency() -> bool:
    build_tools_ready = _install_with_winget(
        "Microsoft.VisualStudio.2022.BuildTools",
        extra_args=[
            "--override",
            (
                "--quiet --wait --norestart --nocache "
                "--add Microsoft.VisualStudio.Workload.VCTools "
                "--add Microsoft.VisualStudio.Component.VC.CMake.Project "
                "--includeRecommended"
            ),
        ],
    )
    if not build_tools_ready:
        return False
    return _install_with_winget("Kitware.CMake")


def _install_with_winget(package_id: str, *, extra_args: list[str] | None = None) -> bool:
    winget_path = shutil.which("winget")
    if not winget_path:
        print(f"winget is not available; cannot auto-install {package_id}.")
        return False

    command = [
        winget_path,
        "install",
        "--id",
        package_id,
        "-e",
        "--accept-package-agreements",
        "--accept-source-agreements",
        "--silent",
    ]
    if extra_args:
        command.extend(extra_args)

    result = subprocess.run(command, check=False)
    return result.returncode == 0


def _print_final_outcome(session: InstallerSession, run_paths) -> None:
    if session.product_installation_status == "complete":
        print("Installation completed successfully.")
    else:
        print("Installation failed.")

    print(f"Install root: {session.install_root}")
    if session.failing_step:
        print(f"Failing step: {session.failing_step}")
    if session.error_message:
        print(f"Error: {session.error_message}")

    print(f"Temporary log: {run_paths.log_path}")
    print(f"Temporary report: {run_paths.json_report_path}")

    for dependency in session.dependencies:
        version_suffix = f" [{dependency.version}]" if dependency.version else ""
        print(f"Dependency {dependency.name}: {dependency.status}{version_suffix}")

    install_root = (session.install_root or "").strip()
    if install_root:
        install_root_path = Path(install_root)
        print(f"Install log: {install_root_path / 'logs' / 'install.log'}")
        print(f"Install report: {install_root_path / 'logs' / 'install-report.json'}")
    if session.control_center_url:
        print(f"Control Center URL: {session.control_center_url}")
    if session.control_center_launcher_path:
        print(f"Control Center launcher: {session.control_center_launcher_path}")


def _probe_python_version() -> str | None:
    executable = sys.executable or ""
    if executable and Path(executable).exists():
        return sys.version.split()[0]
    return _capture_first_available_output(
        ["python", "--version"],
        ["python3", "--version"],
    )


def _probe_git_version() -> str | None:
    return _capture_first_available_output(["git", "--version"])


def _probe_node_version() -> str | None:
    node_version = _capture_first_available_output(["node", "--version"])
    npm_version = _capture_first_available_output(["npm", "--version"])
    if not node_version or not npm_version:
        return None
    return f"{node_version}; {_format_banner('npm', npm_version)}"


def _probe_build_tools_version() -> str | None:
    compiler_banner = _capture_first_available_build_tool_output(
        ["cl"],
        ["gcc", "--version"],
        ["clang", "--version"],
    )
    build_driver_banner = _capture_first_available_output(
        ["cmake", "--version"],
        ["nmake", "/?"],
        ["make", "--version"],
    )
    if not compiler_banner or not build_driver_banner:
        return None
    return f"{compiler_banner}; {build_driver_banner}"


def _build_download_progress_callback():
    def on_progress(progress) -> None:
        phase_prefix = _format_phase_prefix(active_step=True)
        position = ""
        if progress.current_index is not None and progress.total_items is not None:
            position = f"[{progress.current_index}/{progress.total_items}] "
        label = progress.label or "download"
        bytes_summary = f"{progress.bytes_downloaded} B"
        if progress.total_bytes is not None:
            bytes_summary = f"{progress.bytes_downloaded}/{progress.total_bytes} B"
        eta_summary = ""
        if progress.eta_seconds is not None:
            eta_summary = f", ETA {progress.eta_seconds:.1f}s"
        line = f"{position}{label}: {bytes_summary}{eta_summary}"
        _emit_progress_line(line, phase_prefix=phase_prefix)

    return on_progress


def _reset_install_progress_tracker() -> None:
    global _install_progress_tracker
    start_monotonic = time.monotonic()
    _install_progress_tracker = InstallProgressTracker(
        start_monotonic=start_monotonic,
        last_output_monotonic=start_monotonic,
    )


def _clear_install_progress_tracker() -> None:
    global _install_progress_tracker
    _install_progress_tracker = None


def _require_install_progress_tracker() -> InstallProgressTracker:
    global _install_progress_tracker
    if _install_progress_tracker is None:
        start_monotonic = time.monotonic()
        _install_progress_tracker = InstallProgressTracker(
            start_monotonic=start_monotonic,
            last_output_monotonic=start_monotonic,
        )
    return _install_progress_tracker


def _print_phase_message(
    step_index: int,
    message: str,
    *,
    complete: bool = False,
    expected_duration_seconds: float | None = None,
    heartbeat_message: str | None = None,
) -> None:
    tracker = _require_install_progress_tracker()
    if complete:
        _mark_step_completed(tracker, step_index)
    else:
        _mark_step_started(
            tracker,
            step_index,
            expected_duration_seconds=expected_duration_seconds,
            heartbeat_message=heartbeat_message,
        )
    _emit_progress_line(
        message,
        phase_prefix=_format_phase_prefix_for_tracker(tracker, step_index, complete=complete),
    )


def _mark_step_started(
    tracker: InstallProgressTracker,
    step_index: int,
    *,
    expected_duration_seconds: float | None = None,
    heartbeat_message: str | None = None,
) -> None:
    tracker.active_step_index = step_index
    tracker.active_step_started_at = time.monotonic()
    tracker.active_step_expected_duration = expected_duration_seconds
    tracker.active_step_heartbeat_message = heartbeat_message


def _mark_step_completed(tracker: InstallProgressTracker, step_index: int) -> None:
    now = time.monotonic()
    if (
        tracker.active_step_index == step_index
        and tracker.active_step_started_at is not None
    ):
        tracker.completed_durations.append(now - tracker.active_step_started_at)
    tracker.active_step_index = None
    tracker.active_step_started_at = None
    tracker.active_step_expected_duration = None
    tracker.active_step_heartbeat_message = None


def _format_phase_prefix(active_step: bool = False) -> str:
    tracker = _install_progress_tracker
    if tracker is None:
        return ""
    step_index = tracker.active_step_index
    if step_index is None:
        return ""
    return _format_phase_prefix_for_tracker(tracker, step_index, complete=False)


def _format_phase_prefix_for_tracker(
    tracker: InstallProgressTracker,
    step_index: int,
    *,
    complete: bool,
) -> str:
    now = time.monotonic()
    elapsed_seconds = max(now - tracker.start_monotonic, 0.0)
    eta_seconds = _estimate_install_eta_seconds(
        tracker,
        step_index=step_index,
        complete=complete,
        current_time=now,
    )
    return (
        f"[{step_index}/{tracker.total_steps} | "
        f"elapsed {_format_elapsed_seconds(elapsed_seconds)} | "
        f"ETA {_format_eta_seconds(eta_seconds)}]"
    )


def _estimate_install_eta_seconds(
    tracker: InstallProgressTracker,
    *,
    step_index: int,
    complete: bool,
    current_time: float | None = None,
) -> float | None:
    current_time = current_time if current_time is not None else time.monotonic()
    average_duration = None
    if tracker.completed_durations:
        average_duration = sum(tracker.completed_durations) / len(tracker.completed_durations)

    current_step_remaining = 0.0
    if not complete and tracker.active_step_index == step_index:
        current_step_remaining = _estimate_active_step_remaining_seconds(
            tracker,
            current_time=current_time,
            average_duration=average_duration,
        )

    remaining_future_steps = tracker.total_steps - step_index
    future_steps_eta = None
    if average_duration is not None:
        future_steps_eta = average_duration * max(remaining_future_steps, 0)

    eta_components = [
        value
        for value in (current_step_remaining, future_steps_eta)
        if value is not None
    ]
    if not eta_components:
        return None
    return sum(eta_components)


def _estimate_active_step_remaining_seconds(
    tracker: InstallProgressTracker,
    *,
    current_time: float,
    average_duration: float | None,
) -> float:
    if tracker.active_step_started_at is None:
        return 0.0

    active_elapsed = max(current_time - tracker.active_step_started_at, 0.0)
    if tracker.active_step_expected_duration is not None:
        return max(tracker.active_step_expected_duration - active_elapsed, 0.0)
    if average_duration is None:
        return 0.0
    return max(average_duration - active_elapsed, 0.0)


def _format_elapsed_seconds(seconds: float) -> str:
    total_seconds = max(int(seconds), 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _format_eta_seconds(seconds: float | None) -> str:
    if seconds is None:
        return "--:--"
    return _format_elapsed_seconds(seconds)


def _start_phase_heartbeat_thread(
    step_index: int,
    *,
    stop_event: threading.Event,
    heartbeat_interval_seconds: float,
) -> threading.Thread:
    poll_interval_seconds = min(
        HEARTBEAT_POLL_INTERVAL_SECONDS,
        max(heartbeat_interval_seconds / 4.0, 0.05),
    )
    thread = threading.Thread(
        target=_phase_heartbeat_worker,
        args=(step_index, stop_event, heartbeat_interval_seconds, poll_interval_seconds),
        daemon=True,
    )
    thread.start()
    return thread


def _phase_heartbeat_worker(
    step_index: int,
    stop_event: threading.Event,
    heartbeat_interval_seconds: float,
    poll_interval_seconds: float,
) -> None:
    while not stop_event.wait(poll_interval_seconds):
        tracker = _install_progress_tracker
        if tracker is None:
            continue
        if tracker.active_step_index != step_index:
            continue

        last_output_monotonic = tracker.last_output_monotonic
        if last_output_monotonic is None:
            continue
        if time.monotonic() - last_output_monotonic < heartbeat_interval_seconds:
            continue

        heartbeat_message = (
            tracker.active_step_heartbeat_message or "Installation step is still running..."
        )
        _emit_progress_line(
            heartbeat_message,
            phase_prefix=_format_phase_prefix_for_tracker(
                tracker,
                step_index,
                complete=False,
            ),
        )


def _emit_progress_line(message: str, *, phase_prefix: str = "") -> None:
    tracker = _install_progress_tracker
    if tracker is not None:
        tracker.last_output_monotonic = time.monotonic()
    if phase_prefix:
        print(f"{phase_prefix} {message}")
        return
    print(message)


def _capture_first_available_output(*command: list[str]) -> str | None:
    for parts in command:
        if not shutil.which(parts[0]):
            continue
        first_line = _capture_first_output_line(parts)
        if first_line:
            return first_line
    return None


def _capture_first_output_line(command: list[str]) -> str | None:
    result = _run_command(command)
    if result is None or result.returncode != 0:
        return None
    return _extract_first_nonempty_line(result.stdout, result.stderr)


def _capture_first_available_build_tool_output(*command: list[str]) -> str | None:
    for parts in command:
        if not shutil.which(parts[0]):
            continue
        result = _run_command(parts)
        if result is None:
            continue
        first_line = _extract_first_nonempty_line(result.stdout, result.stderr)
        if not first_line:
            continue
        if result.returncode == 0 or _is_recognized_msvc_banner(parts, first_line):
            return first_line
    return None


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return None

def _extract_first_nonempty_line(*outputs: str) -> str | None:
    for output in outputs:
        for line in output.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped
    return None


def _is_recognized_msvc_banner(command: list[str], banner: str) -> bool:
    if not command or command[0].lower() != "cl":
        return False
    return banner.startswith("Microsoft (R) C/C++") and "Compiler Version" in banner


def _format_banner(tool_name: str, banner: str) -> str:
    lowered = banner.lower()
    if lowered.startswith(f"{tool_name} "):
        return banner
    return f"{tool_name} {banner}"
