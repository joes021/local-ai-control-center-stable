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


def test_windows_installer_entry_prefers_repo_src_before_importing_package():
    entry_script = Path("packaging/windows_installer_entry.py").read_text(encoding="utf-8")

    assert 'Path(__file__).resolve().parents[1] / "src"' in entry_script
    assert "sys.path.insert(0, str(_REPO_SRC))" in entry_script


def test_build_windows_installer_script_creates_latest_setup_alias():
    script = Path("packaging/build_windows_installer.ps1").read_text(encoding="utf-8")

    assert "LocalAIControlCenterSetup-latest.exe" in script
    assert "Copy-Item $versionedSetupPath $latestSetupPath -Force" in script


def test_build_windows_installer_script_can_skip_npm_when_node_modules_are_already_present():
    script = Path("packaging/build_windows_installer.ps1").read_text(encoding="utf-8")

    assert '$npmCommandSource = Get-Command "npm.cmd" -ErrorAction SilentlyContinue' in script
    assert 'elseif (-not (Test-Path $frontendTsc) -or -not (Test-Path $frontendVite))' in script
    assert 'throw "npm is required to install missing frontend dependencies."' in script


def test_publish_github_release_script_uploads_latest_setup_alias():
    script = Path("packaging/publish_github_release.ps1").read_text(encoding="utf-8")

    assert "LocalAIControlCenterSetup-latest.exe" in script
    assert "gh release" in script
    assert 'cmd /c "gh release view $tag --repo $Repository 1>nul 2>nul"' in script
    assert "$releaseExists = $LASTEXITCODE -eq 0" in script
    assert "releases/latest/download/LocalAIControlCenterSetup-latest.exe" not in script


def test_readme_promotes_direct_latest_setup_download():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "LocalAIControlCenterSetup-latest.exe" in readme
    assert "releases/latest/download/LocalAIControlCenterSetup-latest.exe" in readme
    assert "LocalAIControlCenterSetup-v0.4.37.exe" not in readme
