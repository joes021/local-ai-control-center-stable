from pathlib import Path

import pytest

from local_ai_control_center_installer import control_center_startup as startup_module
from local_ai_control_center_installer.control_center_runtime import ControlCenterRuntimeDeployment
from local_ai_control_center_installer.control_center_startup import run_startup_sequence


def test_run_startup_sequence_deploys_launches_and_opens_browser(tmp_path: Path):
    install_root = tmp_path / "install-root"
    expected_install_root = install_root.resolve()
    deployment = ControlCenterRuntimeDeployment(
        install_root=expected_install_root,
        panel_root=install_root / "control-center",
        executable_path=install_root / "control-center" / "local-ai-control-center-panel",
        launcher_path=install_root / "control-center" / "Open-RuntimePilot.cmd",
        command=("python.exe", "-m", "local_ai_control_center_installer.control_center_panel"),
        url="http://127.0.0.1:3210/",
        port=3210,
        access_mode="local-only",
        strategy="python-fallback",
    )
    calls: list[str] = []

    def fake_builder(*, install_root: Path, current_python: str):
        assert install_root == expected_install_root
        calls.append(f"build:{current_python}")
        return deployment

    def fake_launch(received_deployment, *, timeout_seconds=30.0):
        assert received_deployment == deployment
        calls.append(f"launch:{timeout_seconds}")
        return deployment

    def fake_open_browser(url: str):
        calls.append(f"browser:{url}")
        return True

    result = run_startup_sequence(
        install_root=install_root,
        current_python="C:\\Python313\\pythonw.exe",
        deployment_builder=fake_builder,
        launch_runtime=fake_launch,
        open_browser=fake_open_browser,
    )

    assert result == deployment
    assert calls == [
        "build:C:\\Python313\\pythonw.exe",
        "launch:30.0",
        "browser:http://127.0.0.1:3210/",
    ]


def test_startup_open_browser_uses_startfile_fallback_on_windows(monkeypatch):
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(startup_module.os, "name", "nt", raising=False)
    monkeypatch.setattr(startup_module.webbrowser, "open", lambda url: False)
    monkeypatch.setattr(
        startup_module.os,
        "startfile",
        lambda url: calls.append(("startfile", url)),
        raising=False,
    )

    opened = startup_module._open_browser("http://127.0.0.1:3210/")

    assert opened is True
    assert calls == [("startfile", "http://127.0.0.1:3210/")]


def test_run_startup_sequence_raises_when_browser_cannot_open(tmp_path: Path):
    install_root = tmp_path / "install-root"
    deployment = ControlCenterRuntimeDeployment(
        install_root=install_root.resolve(),
        panel_root=install_root / "control-center",
        executable_path=install_root / "control-center" / "local-ai-control-center-panel",
        launcher_path=install_root / "control-center" / "Open-RuntimePilot.cmd",
        command=("python.exe", "-m", "local_ai_control_center_installer.control_center_panel"),
        url="http://127.0.0.1:3210/",
        port=3210,
        access_mode="local-only",
        strategy="python-fallback",
    )

    with pytest.raises(RuntimeError, match="Browser nije mogao da se otvori"):
        run_startup_sequence(
            install_root=install_root,
            current_python="C:\\Python313\\pythonw.exe",
            deployment_builder=lambda **kwargs: deployment,
            launch_runtime=lambda received_deployment, timeout_seconds=30.0: deployment,
            open_browser=lambda url: False,
        )
