# 15-minute walkthrough

A scripted tour for someone seeing the hub for the first time. Useful as
an interview talking-track or a Loom video script.

## 0 — Setup (1 min)

`./setup.ps1` (or `./setup.sh`). The script:
1. Installs Playwright + the browser (chromium only — ~120 MB).
2. Creates the hub's Python venv + installs Flask/waitress/openpyxl/etc.
3. Seeds `run_history.json` (17 entries, 2 weeks), `schedules.json` (1
   daily smoke run), and `bugs/saucedemo-e2e.json` (4 bugs).
4. Starts the hub at <http://localhost:8080>.

## 1 — Saucedemo Playwright suite (3 min)

```bash
cd projects/saucedemo
npm test
```

17 tests pass against the live `saucedemo.com` in ~17 seconds.

Show:
- `tests/pages/LoginPage.ts` — `TEST_USERS` const documents saucedemo's
  six test users (`standard`, `locked`, `problem`, `performance`,
  `error`, `visual`). Test bodies read like requirements:
  `await login.loginAs("standard")`.
- `tests/e2e/TS_06_problem_user.visual.spec.ts` — `problem_user` serves
  the same dog photo for every product. We assert that all six product
  `<img src>` values collapse to a single unique URL — stronger than a
  pixel-diff baseline because it survives OS rendering differences in CI.
  A full-page screenshot is still saved as evidence for the release gate.
- `npm run test:smoke` — 4 tests in 12 seconds, hub-tag-compatible.

## 2 — Hub dashboard tour (5 min)

Open <http://localhost:8080>. Walk through:

### Projects tab
- 2 projects registered: `saucedemo-e2e` (active) + `saucedemo-mobile`
  (planning — phase=planning is a real signal: release gate skips it).
- Click `saucedemo-e2e` → dashboard switches scope.

### Dashboard
- Trend chart shows the seeded history. Note the dip on **2026-05-01**
  (3 fails out of 17) — that's the friday-deploy bad-luck pattern, baked
  into seed data on purpose.
- Stats row: total runs, pass rate, open bugs.

### Pipeline tab
- For `playwright-only` type the only stage is **5. Run Tests**. Click
  ▶ to spawn `npx playwright test --reporter=list --grep @<tag>` from
  the project's folder. Output streams via SSE.

### Bug Tracker tab
- 4 bugs of varying severity: 1 Medium open, 1 Low open, 1 Low fixed,
  1 High closed. Aging badges show how long each has been open.

### Schedule tab
- 1 daily schedule fires at 02:00 UAT, smoke tag. The seed data shows
  it has run 12 times with one bad night.

### Release Gate tab
- Verdict `GO` / `NOGO` / `NOT_READY` based on 6 criteria for
  `playwright-only` projects: run scope, pass rate ≥ 80%, no Critical
  bugs, no High bugs, screenshots, HTML report.

## 3 — Architecture conversation (5 min)

Open `docs/ARCHITECTURE.md` (or sketch). Key points:

- **State is just JSON files** — `config.json`, `run_history.json`,
  `schedules.json`, `bugs/<id>.json`. No database. Easy to back up,
  diff, version, share.
- **Hub doesn't run tests itself** — it orchestrates. Stage 5 spawns
  `npx playwright test` from the project's working directory and
  streams stdout via Server-Sent Events.
- **Two UIs share one backend** — `/` is a vanilla-JS dashboard,
  `/v2/` is Vue 3 (strangler-fig migration in progress). Same `/api/*`
  endpoints serve both. Demonstrates an opt-in modernisation strategy.
- **Tag system flows end-to-end** — same `@smoke @e2e @regression
  @visual` markers gate Playwright's `--grep`, the hub's stage-5
  dropdown, the schedule definition, and (via run_history's `tag`
  field) the release gate's "Run scope" criterion.

## 4 — What I'd build next (1 min)

(Closes the demo on a forward-looking note.)

- **Live deployment** — Render or Fly.io. Free tier, cold-start ~30s.
- **Mobile viewport project** — `saucedemo-mobile` already registered
  as `phase=planning`. Activate with a Pixel 7 viewport profile in
  `playwright.config.ts`, add visual snapshots.
- **Allure report** — replace pytest-html for richer per-test trends.
- **Slack webhook** — fail notifications on schedule runs.
