[CmdletBinding()]
param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).ProviderPath
$distRoot = Join-Path $repoRoot "dist"
$buildRoot = Join-Path $repoRoot "build"
$specPath = $null

Push-Location $repoRoot
try {
    & $PythonExe -m pip install .[release]
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install release build dependencies."
    }

    $setupFileName = (
        & $PythonExe -c "from pathlib import Path; import sys, tomllib; sys.path.insert(0, 'src'); from local_ai_control_center_installer.windows_release import build_versioned_setup_name; version = tomllib.loads(Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version']; print(build_versioned_setup_name(version))"
    ).Trim()
    if (-not $setupFileName) {
        throw "Failed to resolve versioned setup filename."
    }

    $setupBaseName = [System.IO.Path]::GetFileNameWithoutExtension($setupFileName)
    $specPath = Join-Path $repoRoot "$setupBaseName.spec"

    if (Test-Path $specPath) {
        Remove-Item -Force $specPath
    }

    & $PythonExe -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --console `
        --name $setupBaseName `
        --paths src `
        --collect-data local_ai_control_center_installer `
        packaging/windows_installer_entry.py
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed."
    }

    Write-Host "Built installer:"
    Write-Host (Join-Path $distRoot $setupFileName)
}
finally {
    if ($specPath -and (Test-Path $specPath)) {
        Remove-Item -Force $specPath
    }
    Pop-Location
}
