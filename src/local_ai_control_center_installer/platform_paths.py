from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
import os
import subprocess
import sys

WINDOWS_INSTALL_ROOT_DIRNAME = "LocalAIControlCenter"
LINUX_INSTALL_ROOT_DIRNAME = "local-ai-control-center"


@dataclass(frozen=True)
class WorkerLaunchSpec:
    command: tuple[str, ...]
    env: dict[str, str]
    creationflags: int


def is_windows_platform(platform: str | None = None) -> bool:
    normalized = (platform or sys.platform).lower()
    return normalized.startswith("win")


def is_linux_x86_64_platform(
    *,
    platform_system: str | None = None,
    platform_machine: str | None = None,
) -> bool:
    normalized_system = (platform_system or sys.platform).strip().lower()
    normalized_machine = (platform_machine or "").strip().lower()
    if not normalized_machine and normalized_system == "linux":
        try:
            import platform as platform_module
        except ImportError:  # pragma: no cover
            return False
        normalized_machine = platform_module.machine().strip().lower()
    return normalized_system == "linux" and normalized_machine in {"x86_64", "amd64"}


def hidden_subprocess_creationflags(platform: str | None = None) -> int:
    if not is_windows_platform(platform):
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def detached_subprocess_creationflags(platform: str | None = None) -> int:
    if not is_windows_platform(platform):
        return 0
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    flags |= getattr(subprocess, "DETACHED_PROCESS", 0)
    flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    flags |= getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
    return flags


def new_console_subprocess_creationflags(platform: str | None = None) -> int:
    if not is_windows_platform(platform):
        return 0
    return getattr(subprocess, "CREATE_NEW_CONSOLE", 0)


def default_install_root_for_platform(
    platform: str | None = None,
    *,
    home_path: Path | None = None,
) -> Path:
    normalized_platform = (platform or sys.platform).strip().lower()
    resolved_home = Path.home() if home_path is None else Path(home_path)
    if normalized_platform == "linux":
        return resolved_home / LINUX_INSTALL_ROOT_DIRNAME
    return resolved_home / WINDOWS_INSTALL_ROOT_DIRNAME


def prepend_pythonpath(
    src_root: Path,
    existing_pythonpath: str | None,
    *,
    path_separator: str | None = None,
) -> str:
    normalized_src_root = str(src_root)
    normalized_existing = (existing_pythonpath or "").strip()
    separator = os.pathsep if path_separator is None else path_separator
    if not normalized_existing:
        return normalized_src_root
    return f"{normalized_src_root}{separator}{normalized_existing}"


def build_worker_launch_spec(
    *,
    frozen: bool,
    executable: str | Path,
    src_root: Path,
    install_root: Path,
    worker_flag: str,
    worker_module: str,
    worker_args: list[str] | tuple[str, ...],
    environment: Mapping[str, str] | None = None,
    platform: str | None = None,
    path_separator: str | None = None,
) -> WorkerLaunchSpec:
    env = dict(os.environ if environment is None else environment)
    normalized_executable = str(executable)
    normalized_install_root = str(install_root)
    normalized_args = [str(arg) for arg in worker_args]

    if frozen:
        command = (
            normalized_executable,
            worker_flag,
            "--install-root",
            normalized_install_root,
            *normalized_args,
        )
    else:
        env["PYTHONPATH"] = prepend_pythonpath(
            src_root,
            env.get("PYTHONPATH", ""),
            path_separator=path_separator,
        )
        command = (
            normalized_executable,
            "-m",
            worker_module,
            "--install-root",
            normalized_install_root,
            *normalized_args,
        )

    return WorkerLaunchSpec(
        command=command,
        env=env,
        creationflags=hidden_subprocess_creationflags(platform),
    )


def build_open_url_command(
    url: str,
    *,
    platform: str | None = None,
) -> tuple[str, ...]:
    if is_windows_platform(platform):
        return (
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f"Start-Process '{url}'",
        )
    return ("xdg-open", url)


def run_release_entry(
    *,
    main_fn: Callable[[], int],
    panel_main_fn: Callable[[list[str] | None], int],
    uninstall_main_fn: Callable[[list[str] | None], int],
    update_worker_main_fn: Callable[[list[str] | None], int],
    model_download_worker_main_fn: Callable[[list[str] | None], int],
    pause_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    frozen: bool | None = None,
    argv: list[str] | None = None,
    pause_in_frozen_mode: bool = False,
) -> int:
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    argv = list(sys.argv if argv is None else argv)
    if "--panel" in argv:
        panel_index = argv.index("--panel")
        return panel_main_fn(argv[panel_index + 1 :])
    if "--uninstall" in argv:
        uninstall_index = argv.index("--uninstall")
        return uninstall_main_fn(argv[uninstall_index + 1 :])
    if "--update-install-worker" in argv:
        update_worker_index = argv.index("--update-install-worker")
        return update_worker_main_fn(argv[update_worker_index + 1 :])
    if "--model-download-worker" in argv:
        model_download_worker_index = argv.index("--model-download-worker")
        return model_download_worker_main_fn(argv[model_download_worker_index + 1 :])
    try:
        return main_fn()
    finally:
        if pause_in_frozen_mode and frozen:
            sys.stdout.flush()
            sys.stderr.flush()
            try:
                pause_fn("Press Enter to close the installer window...")
            except EOFError:
                pass
            except KeyboardInterrupt:
                output_fn("")
