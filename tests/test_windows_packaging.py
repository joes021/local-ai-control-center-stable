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


def test_build_windows_installer_script_packages_repo_data_instead_of_site_packages_collect():
    script = Path("packaging/build_windows_installer.ps1").read_text(encoding="utf-8")

    assert "--collect-data local_ai_control_center_installer" not in script
    assert '$packageRoot = Join-Path $repoRoot "src' in script
    assert "local_ai_control_center_installer" in script
    assert '"--add-data"' in script
    assert '"$($mapping.Source);$($mapping.Destination)"' in script
    assert "control_center_backend" in script
    assert "frontend_dist" in script
    assert "turboquant_sidecars" in script
    assert "manifests" in script
