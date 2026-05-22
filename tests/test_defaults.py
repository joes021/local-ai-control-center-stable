import pytest

import local_ai_control_center_installer.defaults as defaults_module
from local_ai_control_center_installer.session import InstallerSession


def test_default_scan_dependencies_attempts_automatic_installs_for_missing_required_tools(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    session = InstallerSession()
    probe_values = {
        "python": "3.13.7",
        "git": None,
        "node": None,
        "build-tools": None,
    }
    install_calls: list[str] = []

    def fake_git_install() -> bool:
        install_calls.append("git")
        probe_values["git"] = "git version 2.49.0.windows.1"
        return True

    def fake_node_install() -> bool:
        install_calls.append("node")
        probe_values["node"] = "v22.15.0; npm 10.9.2"
        return True

    def fake_build_tools_install() -> bool:
        install_calls.append("build-tools")
        probe_values["build-tools"] = (
            "Microsoft (R) C/C++ Optimizing Compiler Version 19.39.33523 for x64; "
            "cmake version 3.31.6"
        )
        return True

    monkeypatch.setattr(defaults_module, "_probe_python_version", lambda: probe_values["python"])
    monkeypatch.setattr(defaults_module, "_probe_git_version", lambda: probe_values["git"])
    monkeypatch.setattr(defaults_module, "_probe_node_version", lambda: probe_values["node"])
    monkeypatch.setattr(
        defaults_module,
        "_probe_build_tools_version",
        lambda: probe_values["build-tools"],
    )
    monkeypatch.setattr(
        defaults_module,
        "_build_dependency_install_strategies",
        lambda: {
            "git": fake_git_install,
            "node": fake_node_install,
            "build-tools": fake_build_tools_install,
        },
    )

    updated = defaults_module.default_scan_dependencies(session)
    captured = capsys.readouterr()

    assert updated is session
    assert install_calls == ["git", "node", "build-tools"]
    assert [record.status for record in updated.dependencies] == [
        "ready",
        "ready",
        "ready",
        "ready",
    ]
    assert [record.version for record in updated.dependencies] == [
        "3.13.7",
        "git version 2.49.0.windows.1",
        "v22.15.0; npm 10.9.2",
        "Microsoft (R) C/C++ Optimizing Compiler Version 19.39.33523 for x64; cmake version 3.31.6",
    ]
    assert "Missing dependency detected: git" in captured.out
    assert "Automatic install succeeded: build-tools" in captured.out


def test_default_scan_dependencies_surfaces_failed_automatic_install_attempt(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    session = InstallerSession()

    monkeypatch.setattr(defaults_module, "_probe_python_version", lambda: "3.13.7")
    monkeypatch.setattr(defaults_module, "_probe_git_version", lambda: None)
    monkeypatch.setattr(defaults_module, "_probe_node_version", lambda: "v22.15.0; npm 10.9.2")
    monkeypatch.setattr(
        defaults_module,
        "_probe_build_tools_version",
        lambda: "Microsoft (R) C/C++ Optimizing Compiler Version 19.39.33523 for x64; cmake version 3.31.6",
    )
    monkeypatch.setattr(
        defaults_module,
        "_build_dependency_install_strategies",
        lambda: {"git": lambda: False},
    )

    updated = defaults_module.default_scan_dependencies(session)
    captured = capsys.readouterr()

    git_record = next(record for record in updated.dependencies if record.name == "git")
    assert git_record.status == "failed-install"
    assert git_record.install_attempted is True
    assert git_record.install_succeeded is False
    assert "Automatic install failed: git" in captured.out
