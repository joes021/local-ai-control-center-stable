from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH_PATH = REPO_ROOT / "bootstrap" / "install.sh"


def test_install_sh_prefers_python3_and_runs_python_core_entrypoint():
    script = INSTALL_SH_PATH.read_text(encoding="utf-8")

    assert script.startswith("#!/usr/bin/env bash")
    assert "python_candidates=(" in script
    assert 'python_command="$(command -v "${candidate}")"' in script
    assert '"${python_command}" -m local_ai_control_center_installer.main' in script


def test_install_sh_checks_versioned_python_candidates_before_plain_python3():
    script = INSTALL_SH_PATH.read_text(encoding="utf-8")

    assert "python_candidates=(" in script
    assert "python3.13" in script
    assert "python3.12" in script
    assert "python3.11" in script
    assert "python3\n  python" in script


def test_install_sh_exports_pythonpath_with_linux_separator():
    script = INSTALL_SH_PATH.read_text(encoding="utf-8")

    assert 'export PYTHONPATH="${src_root}${PYTHONPATH:+:${PYTHONPATH}}"' in script
    assert 'cd "${repo_root}"' in script


def test_install_sh_surfaces_missing_python_requirement_honestly():
    script = INSTALL_SH_PATH.read_text(encoding="utf-8")

    assert 'Python 3.11+ was not found on PATH.' in script
    assert 'Bootstrap cannot continue without Python.' in script
