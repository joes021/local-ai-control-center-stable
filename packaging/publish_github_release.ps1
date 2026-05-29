[CmdletBinding()]
param(
    [string]$Version,
    [string]$Title,
    [string]$Repository = "joes021/local-ai-control-center-stable"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).ProviderPath
$distRoot = Join-Path $repoRoot "dist"

Push-Location $repoRoot
try {
    if (-not $Version) {
        $Version = (
            python -c "from pathlib import Path; import tomllib; print(tomllib.loads(Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version'])"
        ).Trim()
    }
    if (-not $Version) {
        throw "Failed to resolve version from pyproject.toml."
    }

    $tag = "v$Version"
    if (-not $Title) {
        $Title = "$tag"
    }

    $versionedSetupName = "LocalAIControlCenterSetup-$tag.exe"
    $latestSetupName = "LocalAIControlCenterSetup-latest.exe"
    $checksumName = "SHA256SUMS-$tag.txt"
    $wheelName = "local_ai_control_center_installer-$Version-py3-none-any.whl"
    $sdistName = "local_ai_control_center_installer-$Version.tar.gz"
    $notesPath = Join-Path $distRoot "release-notes-$tag.md"

    $versionedSetupPath = Join-Path $distRoot $versionedSetupName
    $latestSetupPath = Join-Path $distRoot $latestSetupName
    $checksumPath = Join-Path $distRoot $checksumName
    $wheelPath = Join-Path $distRoot $wheelName
    $sdistPath = Join-Path $distRoot $sdistName

    foreach ($requiredPath in @($versionedSetupPath, $wheelPath, $sdistPath, $checksumPath, $notesPath)) {
        if (-not (Test-Path $requiredPath)) {
            throw "Missing release artifact: $requiredPath"
        }
    }

    Copy-Item $versionedSetupPath $latestSetupPath -Force

    $assets = @(
        $versionedSetupPath,
        $latestSetupPath,
        $wheelPath,
        $sdistPath,
        $checksumPath
    )

    & gh release view $tag --repo $Repository 1>$null 2>$null
    $releaseExists = $LASTEXITCODE -eq 0
    if ($releaseExists) {
        & gh release upload $tag @assets --repo $Repository --clobber
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to upload release assets."
        }

        & gh release edit $tag --repo $Repository --title $Title --notes-file $notesPath
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to update release metadata."
        }
    }
    else {
        & gh release create $tag @assets --repo $Repository --title $Title --notes-file $notesPath
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create GitHub release."
        }
    }
}
finally {
    Pop-Location
}
