from pathlib import Path


def test_build_windows_installer_script_cleans_build_root_before_pip_install():
    script = Path("packaging/build_windows_installer.ps1").read_text(encoding="utf-8")

    cleanup_marker = "Remove-Item -Recurse -Force $buildRoot"
    requirements_marker = "optional-dependencies', {}).get('release', [])"
    pip_install_marker = "& $PythonExe -m pip install @releaseRequirements"

    assert cleanup_marker in script
    assert requirements_marker in script
    assert pip_install_marker in script
    assert script.index(cleanup_marker) < script.index(pip_install_marker)
    assert "pip install .[release]" not in script
