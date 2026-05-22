import pytest

import local_ai_control_center_installer.defaults as defaults_module
from local_ai_control_center_installer.session import InstallerSession


def test_default_scan_dependencies_tracks_only_runtime_prerequisites_for_prebuilt_installer(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    session = InstallerSession()
    install_calls: list[str] = []

    monkeypatch.setattr(defaults_module, "_probe_python_version", lambda: "3.13.7")
    monkeypatch.setattr(defaults_module, "_probe_git_version", lambda: None)
    monkeypatch.setattr(defaults_module, "_probe_node_version", lambda: None)
    monkeypatch.setattr(
        defaults_module,
        "_probe_build_tools_version",
        lambda: None,
    )
    monkeypatch.setattr(
        defaults_module,
        "_build_dependency_install_strategies",
        lambda: {
            "git": lambda: install_calls.append("git") or True,
            "node": lambda: install_calls.append("node") or True,
            "build-tools": lambda: install_calls.append("build-tools") or True,
        },
    )

    updated = defaults_module.default_scan_dependencies(session)
    captured = capsys.readouterr()

    assert updated is session
    assert install_calls == []
    assert [record.name for record in updated.dependencies] == ["python"]
    assert [record.status for record in updated.dependencies] == ["ready"]
    assert [record.version for record in updated.dependencies] == ["3.13.7"]
    assert "Dependency ready: python (3.13.7)" in captured.out
    assert "Missing dependency detected:" not in captured.out


def test_default_scan_dependencies_surfaces_failed_python_runtime_detection(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    session = InstallerSession()

    monkeypatch.setattr(defaults_module, "_probe_python_version", lambda: None)
    monkeypatch.setattr(defaults_module, "_probe_git_version", lambda: None)
    monkeypatch.setattr(defaults_module, "_probe_node_version", lambda: None)
    monkeypatch.setattr(
        defaults_module,
        "_probe_build_tools_version",
        lambda: None,
    )
    monkeypatch.setattr(
        defaults_module,
        "_build_dependency_install_strategies",
        lambda: {},
    )

    updated = defaults_module.default_scan_dependencies(session)
    captured = capsys.readouterr()

    python_record = next(record for record in updated.dependencies if record.name == "python")
    assert python_record.status == "failed-install"
    assert python_record.install_attempted is True
    assert python_record.install_succeeded is False
    assert "Automatic install failed: python (no packaged strategy)" in captured.out
