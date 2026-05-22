[CmdletBinding()]
param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).ProviderPath
$distRoot = Join-Path $repoRoot "dist"
$buildRoot = Join-Path $repoRoot "build"
$specPath = Join-Path $repoRoot "LocalAIControlCenterSetup.spec"

Push-Location $repoRoot
try {
    & $PythonExe -m pip install .[release]
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install release build dependencies."
    }

    if (Test-Path $specPath) {
        Remove-Item -Force $specPath
    }

    & $PythonExe -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --console `
        --name LocalAIControlCenterSetup `
        --paths src `
        --collect-data local_ai_control_center_installer `
        packaging/windows_installer_entry.py
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed."
    }

    Write-Host "Built installer:"
    Write-Host (Join-Path $distRoot "LocalAIControlCenterSetup.exe")
}
finally {
    if (Test-Path $specPath) {
        Remove-Item -Force $specPath
    }
    Pop-Location
}
