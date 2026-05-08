# Install F180 Hub as a Windows service via NSSM — P1.1 Sprint F.
#
# Usage (run elevated PowerShell):
#   .\scripts\install-service.ps1
#
# Prerequisites:
#   - NSSM installed and on PATH (https://nssm.cc/)
#   - Python on PATH
#
# What it does:
#   1. Verifies nssm + python are reachable
#   2. Removes any existing F180Hub service (idempotent re-run)
#   3. Installs service pointing at scripts\serve_prod.py
#   4. Sets AppDirectory + log files + auto-start
#   5. Starts the service
#
# Uninstall: nssm remove F180Hub confirm

$ErrorActionPreference = 'Stop'

$ServiceName = 'F180Hub'
$HubDir      = (Resolve-Path "$PSScriptRoot\..").Path
$Entrypoint  = Join-Path $HubDir 'scripts\serve_prod.py'
$LogDir      = Join-Path $HubDir 'logs'

if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
    Write-Error "nssm not on PATH. Download from https://nssm.cc/ and add to PATH."
    exit 1
}
$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) {
    Write-Error "python not on PATH."
    exit 1
}

$existing = (& nssm.exe status $ServiceName 2>$null)
if ($LASTEXITCODE -eq 0) {
    Write-Host "Removing existing $ServiceName service"
    & nssm.exe stop $ServiceName confirm 2>$null
    & nssm.exe remove $ServiceName confirm
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Write-Host "Installing $ServiceName via nssm"
& nssm.exe install $ServiceName $PythonExe $Entrypoint
& nssm.exe set $ServiceName AppDirectory   $HubDir
& nssm.exe set $ServiceName AppStdout      (Join-Path $LogDir 'service-stdout.log')
& nssm.exe set $ServiceName AppStderr      (Join-Path $LogDir 'service-stderr.log')
& nssm.exe set $ServiceName AppRotateFiles 1
& nssm.exe set $ServiceName AppRotateBytes 10485760
& nssm.exe set $ServiceName Start          SERVICE_AUTO_START
& nssm.exe set $ServiceName DisplayName    'F180 Hub'
& nssm.exe set $ServiceName Description    'F180 Hub — central QA dashboard'

& nssm.exe start $ServiceName

Write-Host ""
Write-Host "Installed as Windows service '$ServiceName'"
Write-Host "  Status:   nssm status $ServiceName"
Write-Host "  Logs:     Get-Content '$LogDir\service-stdout.log' -Wait -Tail 50"
Write-Host "  Stop:     nssm stop $ServiceName"
Write-Host "  Remove:   nssm remove $ServiceName confirm"
Write-Host ""
Write-Host "Hub should be reachable at http://127.0.0.1:8080 within ~5 seconds."
