# Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Browser (localhost:8080)                      │
│                                                                      │
│  ┌─────────────────────────────┐    ┌──────────────────────────────┐ │
│  │  Legacy dashboard ( / )     │    │  Vue v2 dashboard ( /v2/ )   │ │
│  │  templates/dashboard.html   │    │  hub/frontend/ (vite + pinia)│ │
│  └──────────┬──────────────────┘    └──────────┬───────────────────┘ │
│             │                                  │                     │
│             └─────── fetch /api/* ─────────────┘                     │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────────┐
│                     Flask app (hub/app.py)                           │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  ~70 @app.route handlers                                       │  │
│  │  /api/projects        /api/run/log         /api/release-gate   │  │
│  │  /api/info            /api/run/history     /api/schedules/*    │  │
│  │  /api/status          /api/run/tests (SSE) /api/bugs/*         │  │
│  └─────────┬──────────────────────┬──────────────────┬─────────────┘ │
│            │                      │                  │              │
│  ┌─────────▼─────┐    ┌───────────▼────────┐   ┌─────▼──────┐        │
│  │release_gate.py│    │ Scheduler thread   │   │ validators │        │
│  │ verdict logic │    │ (20 s loop, fires  │   │ (startup)  │        │
│  └───────────────┘    │  schedules.json)   │   └────────────┘        │
│                       └────────────────────┘                         │
└─────────────────────────────────┬────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼────────────────────────────────────┐
│                        State (JSON files)                            │
│                                                                      │
│  config.json        registered projects + email/notification config  │
│  run_history.json   max 500 runs (older flush to monthly archives)   │
│  schedules.json     daily/weekly/cron triggers                       │
│  bugs/<id>.json     one file per project                             │
└─────────────────────────────────┬────────────────────────────────────┘
                                  │
                              spawn / read
                                  │
┌─────────────────────────────────▼────────────────────────────────────┐
│                     Sub-projects (separate repos)                    │
│                                                                      │
│  projects/saucedemo/                                                 │
│    └── npx playwright test --reporter=list --grep @<tag>             │
│        └── stdout streamed back via SSE → run_history.json appended  │
└──────────────────────────────────────────────────────────────────────┘
```

## Why JSON over a database

- **Auditable** — every state change shows up in a diff.
- **Recoverable** — copy/paste a single file to restore.
- **No migration drama** — schema lives in code, not tables.
- **Fast enough** — atomic writes via temp + rename, JSON parse <1 ms
  for our state-file sizes (run_history capped at 500 entries).

The hub does have a `metrics.db` SQLite file that's *not* part of state —
it's a per-instance cache for trend chart aggregations and gets
gitignored.

## Why two dashboards

Legacy `templates/dashboard.html` was the original, written in vanilla
HTML/JS/CSS. Vue v2 is the in-progress modernisation. Both consume the
same `/api/*` endpoints. The strangler-fig gives us:

- Zero-downtime feature work — Vue can ship before legacy is replaced.
- A/B testable — switch between `/` and `/v2/` without redeploying.
- Documented migration path — anyone can grep `templates/dashboard.html`
  to find the legacy implementation of any Vue feature.

## How a Stage-5 run flows

1. User clicks ▶ on the dashboard, picks tag + env.
2. Browser → `GET /api/run/tests?p=saucedemo-e2e&tag=smoke&env=uat` (SSE).
3. Hub looks up project path from `config.json`, spawns
   `npx playwright test --reporter=list --grep @smoke` in
   `projects/saucedemo/`.
4. Hub pipes child stdout into SSE events; dashboard renders them.
5. On exit, hub parses pass/fail counts from the output and appends a
   row to `run_history.json` (no `source` field for manual runs;
   `source: "schedule"` for scheduler-fired runs).
6. Dashboard auto-refreshes the trend chart.

## How the release gate evaluates a project

`release_gate.py::compute_release_gate(pid)` reads from:
- `config.json` projects[].gates (per-project threshold overrides)
- `run_history.json` (last valid run with pass+fail > 0)
- `bugs/<pid>.json` (open Critical / High counts)
- Filesystem (screenshots in `<project>/test-results/**/*.png`,
  `playwright-report/index.html` mtime)

For a `playwright-only` project, six criteria fire:
1. **Run scope** ≥ `@e2e` or `All` (smoke alone is insufficient).
2. **Pass rate** ≥ 80% (configurable).
3. **No Critical** bug `Open`.
4. **No High** bug `Open` (warn band 1-2).
5. **Screenshots present** (TS_*.png or test-results/**/*.png).
6. **HTML report ready** (`playwright-report/index.html` mtime).

Verdict is `GO` if no hard fails; `NOGO` if any hard fail; `NOT_READY`
if no run history yet; `SKIP_PLANNING`/`SKIP_PAUSED` if phase isn't
active.

This separation — runs are evidence, gate is policy — lets the same
suite drive multiple environments without changing test code.
