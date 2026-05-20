from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from local_ai_control_center_installer.apply_phase import apply_bootstrap_phase
from local_ai_control_center_installer.dependencies import scan_all_dependencies
from local_ai_control_center_installer.prompts import collect_installer_answers
from local_ai_control_center_installer.reporting import (
    build_run_paths,
    write_human_log,
    write_json_report,
)
from local_ai_control_center_installer.session import InstallerSession


def default_collect_answers(session: InstallerSession) -> InstallerSession:
    return collect_installer_answers(session)


def default_scan_dependencies(session: InstallerSession) -> InstallerSession:
    return scan_all_dependencies(
        session,
        probes={
            "python": _probe_python_version,
            "git": _probe_git_version,
            "node": _probe_node_version,
            "build-tools": _probe_build_tools_version,
        },
    )


def default_apply_phase(session: InstallerSession) -> InstallerSession:
    return apply_bootstrap_phase(session, temp_root=_default_temp_root())


def default_write_reports(session: InstallerSession) -> None:
    run_paths = build_run_paths(_default_temp_root(), _build_run_id(session))
    write_human_log(session, run_paths.log_path)
    write_json_report(session, run_paths.json_report_path)


def _default_temp_root() -> Path:
    return Path(tempfile.gettempdir())


def _build_run_id(session: InstallerSession) -> str:
    if session.started_at:
        return session.started_at.replace(":", "-")
    return "manual-run"


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
