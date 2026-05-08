# One-command setup for QA Hub Demo (Windows / PowerShell).
# - Installs Python deps for the hub
# - Installs npm deps + chromium for the saucedemo Playwright project
# - Seeds run history / bugs / schedules
# - Starts the hub on http://localhost:8080
#
# Usage: .\setup.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSCommandPath
Set-Location $root

Write-Host "=== 1/4 — Saucedemo Playwright project ===" -ForegroundColor Cyan
Set-Location "$root\projects\saucedemo"
npm install --silent
npx playwright install chromium

Write-Host "`n=== 2/4 — Hub Python venv + deps ===" -ForegroundColor Cyan
Set-Location "$root\hub"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt --quiet

Write-Host "`n=== 3/4 — Seeding demo state ===" -ForegroundColor Cyan
Copy-Item "$root\hub\config.json.example" "$root\hub\config.json" -Force
Copy-Item "$root\_seed_data\run_history.json" "$root\hub\run_history.json" -Force
Copy-Item "$root\_seed_data\schedules.json" "$root\hub\schedules.json" -Force
New-Item -Path "$root\hub\bugs" -ItemType Directory -Force | Out-Null
Copy-Item "$root\_seed_data\bugs\saucedemo-e2e.json" "$root\hub\bugs\saucedemo-e2e.json" -Force

Write-Host "`n=== 4/4 — Starting hub ===" -ForegroundColor Cyan
Write-Host "Hub will start at http://localhost:8080 — Ctrl+C to stop`n"
& .\.venv\Scripts\python.exe app.py
