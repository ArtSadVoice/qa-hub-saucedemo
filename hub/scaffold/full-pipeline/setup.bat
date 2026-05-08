@echo off
chcp 65001 > nul
echo.
echo =====================================================
echo   Feedback180 Test Pipeline — First-Time Setup
echo =====================================================
echo.

REM ── 1. Check Python ───────────────────────────────────
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.10+ from https://python.org
    pause
    exit /b 1
)
echo [OK] Python found

REM ── 2. Check Node.js ──────────────────────────────────
node --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Install Node.js 18+ from https://nodejs.org
    pause
    exit /b 1
)
echo [OK] Node.js found

REM ── 3. Install Python dependencies ────────────────────
echo.
echo Installing Python packages...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] pip install failed
    pause
    exit /b 1
)
echo [OK] Python packages installed

REM ── 4. Install Node dependencies ──────────────────────
echo.
echo Installing Node packages...
npm install
if %errorlevel% neq 0 (
    echo [ERROR] npm install failed
    pause
    exit /b 1
)
echo [OK] Node packages installed

REM ── 5. Install Playwright browsers ────────────────────
echo.
echo Installing Playwright browsers (Chromium)...
npx playwright install chromium
if %errorlevel% neq 0 (
    echo [ERROR] Playwright install failed
    pause
    exit /b 1
)
echo [OK] Playwright browsers installed

REM ── 6. Create .env from example ───────────────────────
if not exist .env (
    if exist .env.example (
        copy .env.example .env > nul
        echo [OK] Created .env from .env.example
        echo      ^> Edit .env to set your BASE_URL if needed
    )
)

REM ── 7. Activate git hooks (template validator on commit) ─
if exist .githooks (
    git config core.hooksPath .githooks > nul 2>&1
    if %errorlevel% equ 0 (
        echo [OK] git hooks activated ^(core.hooksPath = .githooks^)
    ) else (
        echo      ^> not a git repo yet — run "git config core.hooksPath .githooks" after init
    )
)

echo.
echo =====================================================
echo   Setup complete!
echo =====================================================
echo.
echo   Next steps:
echo   1. Place your TCM Excel in input/
echo   2. Verify BASE_URL in tests/e2e/pages/SurveyPage.ts
echo   3. Run:  python web/app.py
echo      Then open:  http://localhost:8080
echo.
pause
