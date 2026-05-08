#Requires -Version 5.1
<#
.SYNOPSIS
    First-time setup for Feedback180 Test Pipeline
.DESCRIPTION
    Installs Python packages, Node packages, and Playwright browsers.
    Run once after cloning / using this template.
.EXAMPLE
    .\setup.ps1
#>

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n[STEP] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "  [OK] $msg"   -ForegroundColor Green }
function Write-Err($msg)  { Write-Host " [ERR] $msg"   -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Yellow
Write-Host "  Feedback180 Test Pipeline — First-Time Setup"        -ForegroundColor Yellow
Write-Host "=====================================================" -ForegroundColor Yellow

# ── 1. Check Python ──────────────────────────────────────
Write-Step "Checking Python..."
try   { $pyVer = python --version 2>&1; Write-Ok $pyVer }
catch { Write-Err "Python not found. Install Python 3.10+ from https://python.org" }

# ── 2. Check Node.js ─────────────────────────────────────
Write-Step "Checking Node.js..."
try   { $nodeVer = node --version 2>&1; Write-Ok "Node $nodeVer" }
catch { Write-Err "Node.js not found. Install Node.js 18+ from https://nodejs.org" }

# ── 3. Python packages ───────────────────────────────────
Write-Step "Installing Python packages..."
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Err "pip install failed" }
Write-Ok "Python packages installed"

# ── 4. Node packages ─────────────────────────────────────
Write-Step "Installing Node packages..."
npm install
if ($LASTEXITCODE -ne 0) { Write-Err "npm install failed" }
Write-Ok "Node packages installed"

# ── 5. Playwright browsers ───────────────────────────────
Write-Step "Installing Playwright browsers (Chromium)..."
npx playwright install chromium
if ($LASTEXITCODE -ne 0) { Write-Err "Playwright install failed" }
Write-Ok "Playwright browsers installed"

# ── 6. .env from example ─────────────────────────────────
if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Ok "Created .env from .env.example — edit it to set BASE_URL"
}

# ── 7. Git hooks ─────────────────────────────────────────
if (Test-Path ".githooks") {
    Write-Step "Activating git hooks (template validation on commit)..."
    git config core.hooksPath .githooks 2>$null
    if ($LASTEXITCODE -eq 0) { Write-Ok "core.hooksPath -> .githooks" }
    else { Write-Host "  (skipped — not a git repo yet)" -ForegroundColor Yellow }
}

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Green
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host "  1. Place your TCM Excel in input/"
Write-Host "  2. Verify BASE_URL in tests/e2e/pages/SurveyPage.ts"
Write-Host "  3. Run:  python web/app.py"
Write-Host "     Then open:  http://localhost:8080"
Write-Host ""
