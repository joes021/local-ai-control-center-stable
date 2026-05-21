[CmdletBinding()]
param()

function Test-PythonRequirement {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CommandPath,
        [string[]]$VersionArgs = @()
    )

    & $CommandPath @VersionArgs -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" *> $null
    return $LASTEXITCODE -eq 0
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).ProviderPath
$srcRoot = Join-Path $repoRoot "src"

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
$pythonArgs = @("-m", "local_ai_control_center_installer.main")

if ($pythonCommand -and -not (Test-PythonRequirement -CommandPath $pythonCommand.Source)) {
    $pythonCommand = $null
}

if (-not $pythonCommand) {
    $pythonCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pythonCommand -and (Test-PythonRequirement -CommandPath $pythonCommand.Source -VersionArgs @("-3"))) {
        $pythonArgs = @("-3", "-m", "local_ai_control_center_installer.main")
    }
    else {
        $pythonCommand = $null
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
