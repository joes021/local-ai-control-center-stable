[CmdletBinding()]
param()

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).ProviderPath
$srcRoot = Join-Path $repoRoot "src"

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
$pythonArgs = @("-m", "local_ai_control_center_installer.main")

if (-not $pythonCommand) {
    $pythonCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $pythonArgs = @("-3.11", "-m", "local_ai_control_center_installer.main")
    }
}

if (-not $pythonCommand) {
    Write-Warning "Python was not found on PATH."
    $attemptInstall = Read-Host "Attempt Python installation now? [y/N]"
    if ($attemptInstall -match "^(?i:y|yes)$") {
        Write-Host "Automatic Python installation is not implemented in this bootstrap slice."
    }
    Write-Error "Bootstrap cannot continue without Python."
    exit 1
}

if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $env:PYTHONPATH = $srcRoot
}
else {
    $env:PYTHONPATH = "$srcRoot;$($env:PYTHONPATH)"
}

Push-Location $repoRoot
try {
    & $pythonCommand.Source @pythonArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
