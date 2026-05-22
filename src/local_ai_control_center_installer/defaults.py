from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from local_ai_control_center_installer.apply_phase import apply_bootstrap_phase
from local_ai_control_center_installer.dependencies import (
    apply_dependency_decision,
    scan_all_dependencies,
)
from local_ai_control_center_installer.download_plan import build_download_plan
from local_ai_control_center_installer.downloads import download_file
from local_ai_control_center_installer.first_run_validation import (
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
    apply_opencode_verification,
)
from local_ai_control_center_installer.runtime_bootstrap import apply_runtime_payload
from local_ai_control_center_installer.server_verification import (
    apply_server_verification,
)
from local_ai_control_center_installer.session import InstallerSession
from local_ai_control_center_installer.turboquant import apply_turboquant


def default_collect_answers(session: InstallerSession) -> InstallerSession:
    return collect_installer_answers(session)


def default_scan_dependencies(session: InstallerSession) -> InstallerSession:
    probes = {
        "python": _probe_python_version,
    }
    session = scan_all_dependencies(
        session,
        probes=probes,
    )
    _attempt_missing_dependency_installs(
        session,
        probes=probes,
        install_strategies=_build_dependency_install_strategies(),
    )
    return session


def default_apply_phase(session: InstallerSession) -> InstallerSession:
    return apply_bootstrap_phase(session, temp_root=_default_temp_root())


def default_prepare_download_plan(session: InstallerSession) -> InstallerSession:
    if session.download_plan is not None or session.bootstrap_status != "ready":
        return session
    print("Preparing download plan...")
    try:
        session.download_plan = build_download_plan(session)
    except (OSError, ValueError):
        session.download_plan = None
    item_count = _count_download_plan_items(session.download_plan)
    if item_count is None:
        print("Download plan unavailable.")
    else:
        print(f"Download plan ready: {item_count} item(s).")
    return session


def default_apply_runtime_payload(session: InstallerSession) -> InstallerSession:
    progress_callback = _build_download_progress_callback()
    return _run_phase_with_status(
        session,
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
        start_message="Verifying local llama.cpp server...",
        status_label="llama.cpp server verification status",
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
        start_message="Verifying OpenCode live route...",
        status_label="OpenCode live-route verification status",
        step_fn=lambda current_session: apply_opencode_verification(
            current_session,
            temp_root=_default_temp_root(),
        ),
        status_getter=lambda current_session: current_session.opencode_verification_status,
    )


def default_apply_first_run_validation(session: InstallerSession) -> InstallerSession:
    return _run_phase_with_status(
        session,
        start_message="Running first-run OpenCode smoke...",
        status_label="First-run smoke status",
        step_fn=lambda current_session: apply_first_run_validation(
            current_session,
            temp_root=_default_temp_root(),
        ),
        status_getter=lambda current_session: current_session.first_run_status,
    )


def default_apply_turboquant(session: InstallerSession) -> InstallerSession:
    return _run_phase_with_status(
        session,
        start_message="Checking TurboQuant...",
        status_label="TurboQuant status",
        step_fn=apply_turboquant,
        status_getter=lambda current_session: current_session.turboquant_status,
    )


def default_apply_product_gate(session: InstallerSession) -> InstallerSession:
    return _run_phase_with_status(
        session,
        start_message="Finalizing installation status...",
        status_label="Product installation status",
        step_fn=apply_product_gate,
        status_getter=lambda current_session: current_session.product_installation_status,
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


def _default_temp_root() -> Path:
    return Path(tempfile.gettempdir())


def _run_phase_with_status(
    session: InstallerSession,
    *,
    start_message: str,
    status_label: str,
    step_fn,
    status_getter,
) -> InstallerSession:
    print(start_message)
    session = step_fn(session)
    print(f"{status_label}: {status_getter(session)}")
    return session


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


def _build_dependency_install_strategies() -> dict[str, callable]:
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
        print(f"{position}{label}: {bytes_summary}{eta_summary}")

    return on_progress


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
