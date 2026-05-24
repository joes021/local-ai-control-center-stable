[CmdletBinding()]
param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).ProviderPath
$distRoot = Join-Path $repoRoot "dist"
$buildRoot = Join-Path $repoRoot "build"
$frontendRoot = Join-Path $repoRoot "frontend"
$frontendPackageDist = Join-Path $repoRoot "src\\local_ai_control_center_installer\\control_center_backend\\frontend_dist"
$frontendTsc = Join-Path $frontendRoot "node_modules\\typescript\\bin\\tsc"
$frontendVite = Join-Path $frontendRoot "node_modules\\vite\\bin\\vite.js"
$specPath = $null

Push-Location $repoRoot
try {
    $npmCommand = if (Get-Command "npm.cmd" -ErrorAction SilentlyContinue) { "npm.cmd" } else { "npm" }
    $nodeCommand = (Get-Command "node" -ErrorAction SilentlyContinue).Source
    if (-not (Test-Path (Join-Path $frontendRoot "package.json"))) {
        throw "Frontend package.json is missing."
    }
    if (-not $nodeCommand) {
        throw "Node.js is required to build the control panel frontend."
    }

    Push-Location $frontendRoot
    try {
        & $npmCommand install
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to install frontend dependencies."
        }

        if (-not (Test-Path $frontendTsc)) {
            throw "Frontend TypeScript compiler is missing."
        }
        if (-not (Test-Path $frontendVite)) {
            throw "Frontend Vite binary is missing."
        }

        & $nodeCommand $frontendTsc -b
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend TypeScript build failed."
        }

        & $nodeCommand $frontendVite build
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend Vite build failed."
        }
    }
    finally {
        Pop-Location
    }

    if (Test-Path $frontendPackageDist) {
        Get-ChildItem $frontendPackageDist -Force | Remove-Item -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $frontendPackageDist | Out-Null
    Copy-Item (Join-Path $frontendRoot "dist\\*") -Destination $frontendPackageDist -Recurse -Force

    if (Test-Path $buildRoot) {
        Remove-Item -Recurse -Force $buildRoot
    }

    $releaseRequirementsOutput = & $PythonExe -c "from pathlib import Path; import tomllib; data = tomllib.loads(Path('pyproject.toml').read_text(encoding='utf-8')); requirements = list(data['project'].get('dependencies', [])) + list(data['project'].get('optional-dependencies', {}).get('release', [])); print('\n'.join(requirements))"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to resolve release build dependencies from pyproject.toml."
    }
    $releaseRequirements = @(
        $releaseRequirementsOutput |
            Where-Object { $_ -and $_.Trim() } |
            ForEach-Object { $_.Trim() }
    )
    if ($releaseRequirements.Count -eq 0) {
        throw "No release build dependencies were resolved from pyproject.toml."
    }

    & $PythonExe -m pip install @releaseRequirements
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
