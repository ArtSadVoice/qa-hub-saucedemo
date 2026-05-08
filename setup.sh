#!/usr/bin/env bash
# One-command setup for QA Hub Demo (macOS / Linux).
# Mirrors setup.ps1 — same 4 steps.
#
# Usage: ./setup.sh

set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
cd "$root"

echo "=== 1/4 — Saucedemo Playwright project ==="
cd "$root/projects/saucedemo"
npm install --silent
npx playwright install chromium

echo
echo "=== 2/4 — Hub Python venv + deps ==="
cd "$root/hub"
[ -d .venv ] || python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip --quiet
./.venv/bin/python -m pip install -r requirements.txt --quiet

echo
echo "=== 3/4 — Seeding demo state ==="
cp "$root/hub/config.json.example" "$root/hub/config.json"
cp "$root/_seed_data/run_history.json" "$root/hub/run_history.json"
cp "$root/_seed_data/schedules.json" "$root/hub/schedules.json"
mkdir -p "$root/hub/bugs"
cp "$root/_seed_data/bugs/saucedemo-e2e.json" "$root/hub/bugs/saucedemo-e2e.json"

echo
echo "=== 4/4 — Starting hub ==="
echo "Hub will start at http://localhost:8080 — Ctrl+C to stop"
echo
./.venv/bin/python app.py
