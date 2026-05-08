# QA Hub Demo — Saucedemo Showcase

[![Playwright](https://img.shields.io/badge/Playwright-1.49+-2EAD33?logo=playwright)](https://playwright.dev)
[![pytest](https://img.shields.io/badge/pytest-8+-0A9EDC?logo=pytest)](https://pytest.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A self-contained, end-to-end QA automation platform built around
[saucedemo.com](https://www.saucedemo.com). Combines:

- A **Flask + Vue dashboard** (`hub/`) that aggregates test runs, bugs,
  schedules, and release-readiness across multiple projects.
- A **Playwright TypeScript suite** (`projects/saucedemo/`) targeting
  saucedemo's full purchase flow — login, cart, checkout, logout, plus
  visual regression on the `problem_user` account.
- Pre-loaded **2 weeks of seed data** so the dashboard looks like a
  team has been using it, not like day zero.

> Built as a portfolio piece. Demonstrates Page Object Model design,
> tag-based test organisation, hub orchestration, scheduled runs, release
> gates, and CI-friendly junit/HTML reporting.

## At a glance

```
qa-hub-saucedemo/
├── hub/                       Flask + Vue dashboard
│   ├── app.py                  ~4k LOC of routes (projects, gates, schedules, bugs)
│   ├── frontend/               Vue v2 (vite + pinia)
│   ├── templates/              legacy vanilla-JS dashboard
│   ├── static/                 CSS + bundle output
│   └── tests/                  pytest — 161 tests, run on every push
│
├── projects/saucedemo/        Playwright TS suite
│   ├── tests/pages/             4 page objects (Login/Inventory/Cart/Checkout)
│   ├── tests/e2e/               6 spec files, 17 tests
│   └── playwright.config.ts     hub-compatible (--grep @<tag>)
│
├── _seed_data/                drop-in run_history + bugs + schedules
└── docs/                      ARCHITECTURE.md + TOUR.md
```

## Quick start (5 minutes)

```bash
# Clone + setup
git clone https://github.com/ArtSadVoice/qa-hub-saucedemo.git
cd qa-hub-saucedemo

# 1. Saucedemo Playwright suite
cd projects/saucedemo
npm install
npx playwright install chromium
npm test                       # runs all 17 tests in ~17 s
npm run test:smoke             # 4 tests, < 30 s

# 2. Hub dashboard (Python 3.10+)
cd ../../hub
python -m venv .venv
.venv\Scripts\activate         # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp ../config.json.example config.json
cp ../_seed_data/run_history.json .
cp ../_seed_data/schedules.json .
mkdir -p bugs && cp ../_seed_data/bugs/saucedemo-e2e.json bugs/
python app.py                  # → http://localhost:8080
```

Open <http://localhost:8080>. The hub finds the saucedemo project, shows
its 17 tests, displays the seeded run history (with one trend dip on
2026-05-01), and surfaces 4 bugs of varying severity.

## What the demo shows

### 1. Page Object Model with intent-named users

`tests/pages/LoginPage.ts` exposes a `TEST_USERS` constant that maps
intent-friendly aliases (`standard`, `locked`, `problem`, `performance`)
to saucedemo's actual usernames — so test bodies read like requirements,
not credentials:

```ts
await login.loginAs("standard");   // happy path
await login.loginAs("locked");     // expects error banner
await login.loginAs("problem");    // expects broken images on inventory
```

### 2. Tag-based test organisation

```bash
npm run test:smoke         # 4 tests — happy path sanity, < 30s
npm run test:e2e           # 2 tests — full checkout flows
npm run test:regression    # 10 tests — sort, validation, edge cases
npm run test:visual        # 1 test — problem_user snapshot baseline
```

The hub's Stage 5 button uses the same `@<tag>` filter, so identical
discipline applies whether you run locally or via the dashboard.

### 3. Multi-project hub aggregation

The hub treats each test suite as a registered project. `config.json`
enumerates them, the dashboard groups runs by project, and the release
gate evaluates per-project criteria (run scope, pass rate, open critical
bugs, screenshots, HTML report). The seed data demonstrates two
projects: `saucedemo-e2e` (active) and `saucedemo-mobile` (planning —
the gate skips it until phase = active).

### 4. Scheduled runs + release gate

The seeded `schedules.json` defines one daily smoke run at 02:00 UAT.
The hub's scheduler thread polls every 20 seconds; runs are tagged
`source: "schedule"` in `run_history.json` so manual and automated runs
are distinguishable on the dashboard.

The release gate evaluates 6 criteria for `playwright-only` projects:
test executed, run scope ≥ @e2e, pass rate ≥ 80%, no Critical/High open
bugs, screenshots present, HTML report ready. Verdict is `GO` / `NOGO` /
`NOT_READY` / `SKIP_*`.

### 5. CI-ready

`.github/workflows/pytest.yml` runs the hub's pytest suite on every push.
Saucedemo Playwright tests can be added similarly — junit XML output is
already configured (`test-results/junit.xml`).

## Repo layout in detail

```
hub/
  app.py                       Flask routes: /api/projects, /api/run/log,
                                /api/release-gate, /api/schedules/*, etc.
  release_gate.py              Per-project verdict computation
  validators.py                Schema validation for config.json fields
  templates/dashboard.html     Legacy vanilla-JS dashboard (~2000 LOC)
  static/app.js                Legacy dashboard JS (~4200 LOC)
  frontend/                    Vue v2 (alternative UI at /v2/)
  scaffold/                    Project starter templates (full-pipeline,
                                manual-testing, playwright-only)
  tests/                       161 pytest tests for the hub itself

projects/saucedemo/
  tests/pages/
    LoginPage.ts               TEST_USERS map + loginAs() helper
    InventoryPage.ts           sort, add/remove, logout
    CartPage.ts                list items, checkout, remove
    CheckoutPage.ts            3-step state machine + subtotal parser
  tests/e2e/
    TS_01_login.spec.ts        4 tests (smoke + 3 regression)
    TS_02_inventory.spec.ts    4 tests (smoke + 3 regression)
    TS_03_cart.spec.ts         4 tests (smoke + e2e + 2 regression)
    TS_04_checkout.spec.ts     3 tests (e2e + 2 regression)
    TS_05_logout.spec.ts       1 smoke
    TS_06_problem_user.visual.spec.ts  1 visual baseline

_seed_data/                    See _seed_data/README.md
docs/
  ARCHITECTURE.md              How the hub talks to projects
  TOUR.md                      15-minute walkthrough script
```

## Tech stack

| Layer | Choice | Why |
|-------|--------|-----|
| Test runner | Playwright TS | Industry-standard for web QA, first-class trace viewer |
| Test pattern | Page Object Model | Tests describe intent, helpers describe DOM |
| Hub backend | Flask + waitress | Tiny, Python-native, no node sidecar needed |
| Hub frontend | Vue 3 + vanilla JS legacy | Two UIs sharing the same `/api/*`, demonstrates strangler-fig migration |
| State | JSON files (no DB) | Auditable, cherry-pickable, Git-friendly |
| CI | GitHub Actions | Free, well-known, exposes artifacts |

## Roadmap

- [ ] Live deployment (Render / Railway / Fly.io) with public URL
- [ ] Mobile-viewport visual regression project (`saucedemo-mobile`,
      currently `phase: planning`)
- [ ] Allure report integration
- [ ] Slack webhook for failed schedule notifications
- [ ] Per-test author attribution + flakiness scoring

## License

MIT. Saucedemo is a trademark of Sauce Labs. This project is not
affiliated with Sauce Labs and is intended purely for portfolio
demonstration of QA automation patterns.
