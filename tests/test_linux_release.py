from pathlib import Path, PurePosixPath

from local_ai_control_center_installer.linux_release import run_linux_installer_entry
from local_ai_control_center_installer.platform_paths import (
    build_worker_launch_spec,
    prepend_pythonpath,
)


def test_run_linux_installer_entry_does_not_pause_even_in_frozen_mode():
    prompts: list[str] = []

    exit_code = run_linux_installer_entry(
        main_fn=lambda: 0,
        pause_fn=lambda prompt: prompts.append(prompt) or "",
        frozen=True,
    )

    assert exit_code == 0
    assert prompts == []


def test_run_linux_installer_entry_dispatches_update_worker_mode_without_pause():
    calls: list[tuple[str, list[str] | None]] = []
    prompts: list[str] = []

    exit_code = run_linux_installer_entry(
        main_fn=lambda: 1,
        update_worker_main_fn=lambda argv=None: calls.append(("update", argv)) or 0,
        argv=[
            "local-ai-control-center-panel",
            "--update-install-worker",
            "--install-root",
            "/opt/lacc",
            "--action-id",
            "update-123",
        ],
        pause_fn=lambda prompt: prompts.append(prompt) or "",
        frozen=True,
    )

    assert exit_code == 0
    assert calls == [("update", ["--install-root", "/opt/lacc", "--action-id", "update-123"])]
    assert prompts == []


def test_prepend_pythonpath_uses_platform_separator():
    src_root = Path("/workspace/src")

    assert (
        prepend_pythonpath(
            PurePosixPath(src_root),
            "/usr/lib/site-packages",
            path_separator=":",
        )
        == "/workspace/src:/usr/lib/site-packages"
    )
    assert prepend_pythonpath(PurePosixPath(src_root), "", path_separator=":") == "/workspace/src"


def test_build_worker_launch_spec_uses_python_module_path_on_linux():
    spec = build_worker_launch_spec(
        frozen=False,
        executable="/usr/bin/python3",
        src_root=PurePosixPath("/workspace/src"),
        install_root=PurePosixPath("/opt/lacc"),
        worker_flag="--update-install-worker",
        worker_module="pkg.worker",
        worker_args=["--action-id", "update-123"],
        environment={"PYTHONPATH": "/usr/lib/site-packages", "HOME": "/tmp/home"},
        platform="linux",
        path_separator=":",
    )

    assert spec.command == (
        "/usr/bin/python3",
        "-m",
        "pkg.worker",
        "--install-root",
        "/opt/lacc",
        "--action-id",
        "update-123",
    )
    assert spec.env["PYTHONPATH"] == "/workspace/src:/usr/lib/site-packages"
    assert spec.env["HOME"] == "/tmp/home"
    assert spec.creationflags == 0


def test_build_worker_launch_spec_uses_frozen_flag_path_on_linux():
    spec = build_worker_launch_spec(
        frozen=True,
        executable="/opt/lacc/control-center/local-ai-control-center-panel",
        src_root=PurePosixPath("/workspace/src"),
        install_root=PurePosixPath("/opt/lacc"),
        worker_flag="--model-download-worker",
        worker_module="pkg.worker",
        worker_args=["--model-id", "qwen"],
        environment={"PYTHONPATH": "/usr/lib/site-packages"},
        platform="linux",
        path_separator=":",
    )

    assert spec.command == (
        "/opt/lacc/control-center/local-ai-control-center-panel",
        "--model-download-worker",
        "--install-root",
        "/opt/lacc",
        "--model-id",
        "qwen",
    )
    assert spec.env["PYTHONPATH"] == "/usr/lib/site-packages"
    assert spec.creationflags == 0
