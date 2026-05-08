# Install F180 Hub git hooks (Windows) — P1.5 Sprint F.
#
# Copies scripts\git-hooks\* into .git\hooks\ (symlinks need admin on
# Windows so we use plain copy — re-run after editing a hook).
#
# Usage: .\scripts\install-hooks.ps1

$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$HooksSrc = Join-Path $RepoRoot 'scripts\git-hooks'
$HooksDst = Join-Path $RepoRoot '.git\hooks'

if (-not (Test-Path (Join-Path $RepoRoot '.git'))) {
    Write-Error "$RepoRoot is not a git repo"
    exit 1
}

New-Item -ItemType Directory -Force -Path $HooksDst | Out-Null

Get-ChildItem $HooksSrc -File | ForEach-Object {
    $dst = Join-Path $HooksDst $_.Name
    Copy-Item $_.FullName $dst -Force
    Write-Host "Installed $($_.Name) -> .git\hooks\$($_.Name)"
}

Write-Host ""
Write-Host "Hooks installed. Note: re-run this script after editing any hook."
