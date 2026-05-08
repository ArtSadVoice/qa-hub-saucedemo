# Changelog

All notable changes to QA Hub Demo. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning is [SemVer](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **`pytest-only` project type** — first-class support for Python pytest projects (no Excel TCM, no Playwright TS). Stage 5 runs `python -m pytest --junitxml=... --html=test-report.html` from the project's `.venv`, parses junit, appends to `run_history.json` automatically. Stages 7/8/9 wired to the generated `test-report.html`. Schedule action `tests` triggers pytest correctly. Release Gate (5 criteria: test_executed, run_scope, pass_rate, no_critical_bug, no_high_bug). Auto-discover detects `pytest.ini` / `pyproject.toml`. Frontend dropdowns and stage visibility updated. Used by `desktop-automation/` (Electron via Playwright CDP) and `mobile-automation/` (Appium placeholder).

### Reliability & Operations

- **CSP tightening — drop `'unsafe-inline'` from script-src.** Audit found
  30+ `onclick=` attributes in `templates/dashboard.html` that need to
  migrate to `addEventListener` before the directive can be dropped
  without breaking legacy nav. Legacy template also has ~621 inline
  `style="..."` attrs but those stay (Vue v2 also uses `:style="..."`
  bindings extensively). Estimated 6-8h once started — needs its own
  sprint, not a tail-end item. (~6-8h)

### Visualization

- **Heatmap calendar** on Overview — daily test runs / fails for the
  last 30 days, surfaces "Friday deploys fail more often" patterns. (~4h)
- **Bug burn-down chart** in Bug Tracker metrics — open / closed /
  created over time. (~3h)
- **Project relationship graph** — when projects share tags or
  cross-reference each other in bugs, render the dependency edges. (~6h)

### Mobile / Accessibility

- **Mobile bottom nav** + slide-up Project Switcher. Sidebar collapses
  at <640px today but navigation feels cramped — bottom nav better
  matches phone ergonomics. (~5h)
- **Keyboard navigation in tables** — `j`/`k` to move row, `enter` to
  open, `x` to toggle selection. Bug Tracker + Overview Health Matrix
  benefit most. (~3h)

### External integrations

- **Webhook receiver** `/api/hooks/<source>` — accept test results from
  Jenkins / GitHub Actions / GitLab CI so Hub becomes the central
  dashboard even for projects whose CI runs elsewhere. (~4h)
- **iCal export** of Schedule — let teams subscribe to scheduled runs in
  Google Calendar / Outlook. (~2h)
- **Slack thread per bug** — when a bug is created, open a thread in a
  configured channel; subsequent updates / status changes post to the
  same thread. (~5h)

### Power-user / Collaboration

- **Saved filters / views** — Bug Tracker filter combinations like
  "Open Critical bugs in Acme projects" become reusable named views,
  accessible from a sidebar shortcut or `Ctrl+K` palette. (~4h)
- **Sharable filter URLs** — every filter combination becomes a
  copy-pasteable link (the building blocks are there from the v2.4.0
  Command Palette URL-query work). (~2h)
- **Bug comments / @mentions** — threaded discussion per bug, email
  notification on @mention. Currently only one description field. (~6h)

### AI

- **AI bug triage** — paste description → suggest severity, tags, and
  similar existing bugs (dedupe). Leverages the AI provider settings
  already in place. (~5h)
- **Smart release summary** — single-button AI-generated stakeholder
  briefing of release status (verdict + criteria + bug summary).
  Pairs well with the existing 📋 Copy Markdown on Release Gate. (~3h)

### Tech debt to watch

- **Bundle size growth** — 323 KB JS as of v2.7.0 (was ~258 KB at
  start of Sprint C). Code-splitting per route (Vue Router lazy
  imports) would shave the initial load.
- **Async invalidation across tabs** — bug edited in Tab A doesn't
  refresh Tab B until manual refresh. A small event bus or
  Server-Sent Event stream for cross-tab invalidation could fix.
- **`useSSE` doesn't auto-reconnect on transient drops** — currently
  treats every drop as a hard failure. Exponential backoff retry would
  smooth flaky-network UX.

## [2.12.0] — 2026-04-29

### Highlights

Sprint J — Pipeline parity audit. Vue v2 Pipeline diverged from legacy
`templates/dashboard.html` in five places: missing Stage 0, wrong
backend script for Stage 2, misleading "Run All" button, and stages
6/8 had drifted to mean different things between the two UIs. All
fixed in one commit.

### Fixed

- **Stage 0 (Explore Survey Paths) added.** Legacy s0 wires
  Playwright MCP to walk a survey app and produce
  `requirements/survey_map.md` + `FLOW.md` before the BA Agent runs.
  Vue v2 had no entry point — survey-app projects had to drop back
  to legacy `/`. Endpoint `/api/run/explore` was already there;
  this commit just exposes it. Stage shown only for full-pipeline
  + playwright-only project types.

- **Stage 2 endpoint corrected to `/api/run/ba`.**  Vue v2 was
  calling `/api/run/generate` (which runs `run.py` — the Stage 7
  report generator). Legacy s2 calls `/api/run/ba` (which runs
  `orchestrator.py --skip-playwright --no-interactive`). Two
  different scripts behind two stages with the same number — silent
  behavior drift if a user ran the same stage from each UI.

- **Stages 6 / 8 swapped to match legacy semantics.** Same number
  used to mean different things across UIs:
    • Vue v2 s6 was "Screenshot Injection" (auto)
    • Legacy   s6 is  "Manual Update Excel Results" (manual)
    • Vue v2 s8 was "Open Report" (passive — basically a no-op)
    • Legacy   s8 is  "Inject Screenshots" (auto)
  Vue v2 now matches: s6 = manual reminder card, s8 = inject. The
  passive "Open Report" was folded into s9.

- **`⚡ Run All` was a lie.** `/api/run/all` only chains `run.py` +
  `screenshot_injector.py` (= legacy "Report + Inject" combo), not
  all 9 stages. Renamed `runAll` → `runReportInject`; button now
  reads `⚡ Report + Inject` with a tooltip that says exactly what
  fires.

### Added

- **🔍 Review TCM (AI) button on Stage 3.** Calls existing
  `/api/run/review-excel` to run AI quality audit of the Test Case
  Matrix. Mirrors legacy's button.

- **📤 Send Report inline at Stage 9.** Legacy puts the send-report
  flow right at the download step; Vue v2 had buried it as a top-bar
  quick action. Added a Stage 9 `📤 Send Report` button that opens
  the same modal — top-bar quick action stays available.

- **Thai stage descriptions + 📋 Copy folder path buttons.** Every
  stage now has a `descTh` line under its label (matches legacy's
  `tl-desc`). Stages with file outputs get a 📋 button that calls
  `/api/path/<kind>` and copies the absolute path to clipboard.
  New `badge-auto` / `badge-manual` chips next to the label match
  legacy's "🤖 รันคำสั่ง" vs "🧑 ทำเอง" timeline visual.

### Test coverage / build

- 155 pytest + 11 Playwright e2e — all green (no regression).
- Build: **334 KB JS / 114 KB CSS** (+4 KB JS for helpers + new
  stage + Thai descriptions).

## [2.11.0] — 2026-04-28

### Highlights

Sprint I — AI track. Two user-triggered AI features leveraging the
existing `ai_provider.py` infrastructure (Claude CLI default / Anthropic
API opt-in). Output is validated server-side so a hallucinated response
never crashes the UI.

### Added

- **A2 — Smart release summary** (Release Readiness page).
  `POST /api/ai/release-summary` builds a Thai-language stakeholder
  briefing from the live release-gate state + open-bug counts + recent
  flakiness. New AI-summary card renders it inline with `✨ Generate` /
  `↻ Regenerate` + 📋 Copy. Pairs with the existing markdown export
  (same data, two audiences: technical detail vs decision-maker brief).

- **A1 — AI bug triage** (BugEditModal).
  `POST /api/ai/bug-triage` takes title + description + existing open
  bugs and returns JSON with `severity`, `severity_reason`, `tags[]`,
  `similar[]`. Frontend shows a suggestion panel with per-field
  `↳ Apply` buttons — user stays in control, nothing auto-applies.

  Defensive parsing: strips ```` ```json ```` fences if the AI ignores
  the JSON-only directive, returns 502 with the raw output when parsing
  fails. Severity clamped to a known value if the AI invents one;
  similar-bug ids validated server-side against the actual bug list so
  the AI can't reference non-existent ids.

### Fixed

- **TDZ bug in BugEditModal** caught during the e2e regression run:
  the immediate-mode watch on `props.bug` cleared `aiSuggestion` on
  every mount, but the ref was declared after the watch — first call
  hit `Cannot access 'f' before initialization`. Moved the declaration
  above the watch.

### Test coverage / build

- **155 pytest** (+13 in `tests/test_ai_track.py`):
    • Prompt builder unit tests (verdict + bugs in summary prompt;
      existing-bug listing in triage prompt; 30-bug cap on existing list)
    • Endpoint integration via monkey-patched `generate()` — happy path,
      markdown-fence stripping, 502 on hallucinated prose, severity
      clamping to Medium, similar-id filtering, 400 on missing required
      fields.
- 11 Playwright e2e — all green.
- Build: **330 KB JS / 113 KB CSS** (+4 KB JS, +3 KB CSS for AI
  suggestion panel + summary card).

## [2.10.0] — 2026-04-28

### Highlights

Two `[Unreleased]` items shipped together — both wire up infrastructure
that earlier sprints prepared but didn't fully expose to users.

### Added

- **H1 — `/api/metrics` SQLite ring buffer.** Per-minute snapshot of
  rolling window per route into `HUB_DIR/metrics.db`, retention
  bounded by `HUB_METRICS_KEEP_HOURS` (default 168 = 1 week). Hot
  path is untouched — every request still updates the in-memory dict
  so `/api/metrics` answers in microseconds. New `metrics-flush`
  background worker (joins the existing config-backup + audit-archive
  trio) writes one row per (minute, route) and prunes older than
  retention.

  New endpoint: `GET /api/metrics/history?hours=N&route=<path>` returns
  per-minute rows `{ts, route, count, errors, p95_ms, max_ms}` for
  charting historical trends. Survives Hub restart, unlike v2.3.0's
  in-memory metrics strip.

- **H2 — Backup retention dashboard** (`Settings → Backup`).
  v2.8.0 shipped `/api/config/backup/{list,run,restore}` endpoints;
  this release wires the UI:
    • "📸 Snapshot now" button calls `/api/config/backup/run`
    • Daily-snapshot table lists every snapshot (name, ts, size) with
      a per-row "↺ Restore" button that goes through `useConfirm` +
      page reload after success
    • Empty state explains the daily auto-backup behavior when no
      snapshots are present yet
  Eliminates the rollback workflow that previously required SSH /
  manual `cp config_YYYYMMDD.json config.json`.

### Deferred

- **H3 — CSP tightening** (drop `'unsafe-inline'` from `script-src`)
  was on the v2.10 plan but the audit revealed scope: 30+ inline
  `onclick=` attributes in `templates/dashboard.html` need migration
  to `addEventListener` first. Moved back to `[Unreleased]` as a
  dedicated 6-8h sprint instead of a rushed half-hour.

### Test coverage / build

- **142 pytest** (+1 contract test for `/api/metrics/history` shape,
  works with an empty ring buffer since the test process doesn't run
  the flush worker).
- 11 Playwright e2e — all green.
- Build: **326 KB JS / 110 KB CSS** (+3 KB JS for the BackupCard
  table + restore flow).

## [2.9.0] — 2026-04-28

### Highlights

Sprint G — security hardening. Three of the five P2 items from the
production-readiness audit shipped as code; HTTPS becomes a deployment
guide rather than backend changes (Caddy/nginx already work — what was
missing was the docs tying it to Sprint G's threat model).

### Added

- **P2.2 — Security response headers.** Five headers attached via a
  single `@app.after_request` hook using `setdefault()` so a reverse
  proxy that injects them already wins (defense-in-depth, not
  conflict):
    `X-Content-Type-Options: nosniff`
    `X-Frame-Options: DENY` (Hub never embeds in an iframe)
    `Referrer-Policy: same-origin`
    `Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()`
    `Content-Security-Policy: default-src 'self'; … frame-ancestors 'none'`
  The CSP keeps `'unsafe-inline'` for now to match legacy templates;
  tightening it is a tracked Sprint H candidate.

- **P2.3 — In-process rate limiter** (~30 LOC, no `flask-limiter`
  dependency).
    • Write endpoints (POST/PUT/DELETE/PATCH): 60/min per (IP, route).
      Real users won't hit it; a script hammering `/api/bugs/add` gets
      cut off in seconds. Returns 429 with a JSON error.
    • Failed auth: 10/min per IP, **only activates when
      `HUB_PASSWORD` is set** (so a fresh install doesn't 429 on every
      page load).
  Buckets are in-memory — single-process deployment, no Redis. Honors
  `X-Forwarded-For` so the bucket tracks real clients when Hub is
  behind Caddy/nginx.

- **P2.4 — Request body cap.**
  `app.config['MAX_CONTENT_LENGTH'] = 10 MB`, override with
  `HUB_MAX_BODY_MB` env var. Flask returns 413 automatically when
  exceeded. Largest legit POST (config import + bulk-paste recipients)
  is well under 10 MB; this blocks the "stream a gig of nulls" DoS
  class.

### Documented (P2.1)

- New "Security hardening" section in `frontend/PRODUCTION.md` ties
  Sprint G's built-ins to the existing Caddy + nginx config templates,
  spells out when HTTPS is needed (anything beyond `127.0.0.1`), and
  documents `HUB_PASSWORD` / `HUB_MAX_BODY_MB` env-var knobs.

### Test coverage / build

- **141 pytest** (+7 in `tests/test_security.py`):
  header presence (success + 404 paths), write rate limit kick-in,
  per-IP isolation, GET-bypass, 413 on oversized body, normal body
  accepted.
- 11 Playwright e2e — all green.
- Build: 323 KB JS / 109 KB CSS — flat (backend + docs only).

## [2.8.0] — 2026-04-28

### Highlights

Sprint F — five P1 items from the production-readiness audit, all
operational health. With this release Hub recovers from a crash on
its own, snapshots its config daily, archives audit entries on a
schedule, and CI fails PRs that introduce hex literals.

### Added

- **P1.1 — Service installer scripts**
    • `scripts/install-service.sh` (Linux/systemd) — one-shot install:
      creates `f180hub` system user, copies the existing
      `scripts/f180-hub.service` unit (patching `WorkingDirectory` to
      wherever the repo lives), enables + starts. Idempotent re-run.
    • `scripts/install-service.ps1` (Windows/NSSM) — pre-flights `nssm`
      + `python`, removes any previous `QAHubDemo` service, installs
      with auto-start + rotated stdout/stderr.
  Together these turn "Hub crashed, who restarts it?" into a non-issue.

- **P1.2 — Auto config.json backup** + three new endpoints.
  Background daemon snapshots `config.json` once per day into
  `config_backups/config_YYYYMMDD.json` with a rolling N-day
  retention (`HUB_CONFIG_BACKUP_KEEP_DAYS`, default 30). Endpoints:
    `GET  /api/config/backup/list`     — files + mtime + size
    `POST /api/config/backup/restore`  — restore by filename (path-
                                         traversal guard rejects ..)
    `POST /api/config/backup/run`      — trigger an immediate snapshot
                                         before a risky import

- **P1.3 — Audit retention scheduled.** Same daemon-thread pattern as
  P1.2 — calls `archive_old_entries()` daily. Manual
  `POST /api/audit/archive` endpoint stays available. Both share
  a single stop event so an `atexit` drains them on shutdown.
  Workers wake every 60s (not 24h sleep) so Ctrl-C is responsive.
  Skipped under pytest so test runs don't kick off real disk I/O.

- **P1.4 — CI wire-up for `npm run lint:css`.** Added a "Lint CSS"
  step to the `vue-build` job in `.github/workflows/tests.yml`.
  v2.7.0 made `color-no-hex` an error locally; this fails PRs in CI
  on the same condition.

- **P1.5 — Pre-commit hook** + installers.
    • `scripts/git-hooks/pre-commit` — runs `vue-tsc --noEmit` +
      `npm run lint:css` only when frontend/ files are staged. Skipped
      silently for backend-only commits so it doesn't slow them down.
    • `scripts/install-hooks.sh` (symlink) / `.ps1` (copy on Windows
      where symlinks need admin) — one-time setup. `--no-verify` is
      the documented escape hatch for mid-refactor commits.

### Test coverage / build

- **134 pytest** (+4 backup contract tests covering shape, idempotent
  run, path-traversal rejection, and 404 on missing snapshot).
- 11 Playwright e2e — all green.
- Build: **323 KB JS / 109 KB CSS** (flat — only backend + scripts
  changed).
- `npm run lint:css`: 0 errors (now also gating CI).

## [2.7.0] — 2026-04-28

### Highlights

Sprint E Batch 3 — final cleanup item from the v2.1.0 stylelint rollout.
The 150-entry hex baseline is gone; `color-no-hex` now fires as **error**
so any new hex literal in CSS breaks `npm run lint:css` (and CI once the
build job is wired to call it).

### Changed

- **Hex baseline cleanup** across 37 files. Three categories of fix:
    1. Semantic tints → theme tokens (`#1F7A2D` → `var(--success)`,
       `#B25600` → `var(--warn)`, `#C62828` → `var(--danger)`,
       `#1565C0` → `var(--primary)`, soft variants likewise).
    2. Neutral grays / borders → tokens (`#6B7C93` → `var(--muted)`,
       `#DDE3EC` → `var(--border)`, `#F7FAFF` → `var(--bg)`, etc.).
    3. Pure black/white literal hex → CSS keywords (`white` / `black`)
       since `color-no-hex` doesn't flag named colors.
  Trade-off: light-mode tint text now uses the same color as dark mode
  (was: slightly darker shade). Single source of truth per semantic
  role outweighs the minor contrast change.

- **30 intentional hex entries** kept with inline
  `/* stylelint-disable-line color-no-hex */` comments — terminal /
  log box dark colors (`#0d1117`, `#c9d1d9`, `#F85149`, `#56D364`),
  severity coral (`#FF6B5C`), chart accent colors that should stay
  vivid in both modes.

- **Stylelint severity** dropped from `warning` to default (error).
  `npm run lint:css` now exits non-zero on any new hex; the message
  points at the inline-disable escape hatch for legitimate cases.

### Test coverage / build

- 11 Playwright e2e — all green (no regression).
- 130 pytest — unchanged (CSS only).
- Build: **323 KB JS / 109 KB CSS** (flat — net diff was +145/-146,
  almost pure substitution).
- `npm run lint:css`: 0 errors (was: 150 warnings).

## [2.6.0] — 2026-04-28

### Highlights

Sprint E Batch 2 — two larger backlog items, shipped together to round
out the Schedule and Bug Tracker workflows.

### Added

- **Cron preview / next-fire times** in Schedule. New `utils/cron.ts`
  parses standard 5-field cron syntax (wildcards, lists `1,2,3`,
  ranges `1-5`, steps `*/5`, Vixie-style dom-OR-dow). Walks
  minute-by-minute up to a 4-year safety bound to find the next N
  fires. Three UI affordances:
    • Add-form: live "✓ valid · next: <ts>" / "⚠ invalid syntax" hint
    • Schedule list: ▸ toggle on each cron row reveals next-5-fires
      panel (monospace timestamps)
    • List view: invalid-cron entries flagged in red so they don't
      silently never fire
  Deliberately doesn't handle named months / `@hourly` shortcuts /
  seconds — would triple the file for marginal value.

- **Bug bulk actions** in Bug Tracker (table view). New checkbox
  column + "select all visible" header checkbox (with proper
  indeterminate state when partial). Selection surfaces a sticky
  bulk-action bar:
    • ⚪ Close · 🟢 Mark Fixed · 🟠 Re-open
    • 🗑 Delete (with danger confirm)
    • × Clear
  Loops existing `/api/bugs/update` and `/api/bugs/delete` (silent
  per-call to avoid toast spam); single summary toast reports
  `✅ Updated N · ✗ K failed`. Selection auto-drops invalid ids
  when `loadBugs` sees them missing (deleted in another tab).

### Test coverage / build

- 130 pytest + 11 e2e — all green (no regression).
- Build: **323 KB JS / 108 KB CSS** (+5 KB JS for the cron parser
  + bulk-actions logic).

## [2.5.0] — 2026-04-28

### Highlights

Sprint E Batch 1 — two unrelated quick wins, shipped together because
both are small and surface separate footguns the audit didn't catch.

### Added

- **Bulk paste recipients** in `Settings → Email`. Both To / CC lists
  gain a collapsible textarea that accepts comma / semicolon / newline
  separated entries. Parser handles plain emails, `Name <email>`, and
  `"Quoted Name" <email>` forms. Per-row guards: dedupe (case
  insensitive) against existing entries + reject invalid email shape.
  A single toast summarises the result —
  `✅ added 5 · ↺ 2 duplicate · ✗ 1 invalid` — no per-row spam.

- **Audit log retention policy** + `POST /api/audit/archive`.
  `logs/audit.jsonl` was unbounded; on a long-running Hub the
  Activity tab's `tail()` got slower over time. New
  `archive_old_entries(retention_days)`:
    • cutoff = `now - retention_days` (default 90, env var
      `HUB_AUDIT_RETENTION_DAYS`)
    • Recent entries → rewritten in-place via temp file + atomic
      rename
    • Older entries → grouped by month → appended to
      `logs/audit_archive/audit_YYYYMM.jsonl` (mirrors run_history
      archive pattern)
    • Defensive: unparseable / missing-ts lines stay in the live file
      rather than risk losing data we can't classify
    • Holds the audit write lock during the swap so concurrent
      `audit()` calls block briefly
  Set `HUB_AUDIT_RETENTION_DAYS=0` to disable (original behavior).

### Test coverage / build

- 130 pytest (+5 retention tests covering kept/archived split,
  unparseable preservation, no-op when nothing's old enough, the
  disable-via-zero path, and endpoint smoke).
- 11 Playwright e2e — unchanged.
- Build: **318 KB JS / 106 KB CSS** (+2 KB JS for the bulk parser).

## [2.4.0] — 2026-04-28

### Highlights

Quality-of-life day 2 — Command Palette becomes useful for everyday
work, and the Project Health Matrix gains a sparkline so trends
read at a glance.

### Added

- **C1 — Command Palette actions** (`Ctrl+K` / `⌘K`). The palette
  used to only navigate; now it can also pre-configure the
  destination view via URL query parameters:

    🚨 Open Critical bugs       → `/bugs?severity=Critical&status=Open`
    🟠 Open all Open bugs       → `/bugs?status=Open`
    ➕ Add new bug              → `/bugs?action=add` (focuses input)
    📤 Send report              → `/pipeline?action=send-report`
    ⚡ Run all stages           → `/pipeline?action=run-all`
    🚦 Re-evaluate Release Gate → `/release?action=reload`
    📊 Hub metrics              → `/overview`

  BugTracker, Pipeline, and Release each watch `route.query` so
  these commands work even when the user is already on the
  destination page (no full reload needed).

- **B1 — Last-20 sparkline column** on the Overview Project Health
  Matrix. Inline SVG (no chart library) — 20 bars, green=pass /
  red=fail, height proportional to test count so a smoke run looks
  smaller than a regression. Hover tooltip shows the pass/fail
  count. Data from `/api/run/history?p=<id>`, loaded in parallel
  via `Promise.allSettled` so a missing history doesn't break the
  row.

### Test coverage / build

- 11 Playwright e2e — all green (no regression).
- 125 pytest — unchanged (UI-only).
- Build: **316 KB JS / 106 KB CSS** (+3 KB JS for the new
  commands + sparkline + 4 watch handlers).

## [2.3.0] — 2026-04-28

### Highlights

Two Sprint E items shipped together because both touch
`HubOverviewView.vue`:

- **T1 — Group by Company / Category** in the Project Health Matrix.
  Segmented control renders one table section per taxonomy value,
  with the "◌ Other" bucket pinned last for untagged projects.
- **E2 — Hub runtime metrics strip** below the project KPIs. Pulls
  `/api/metrics` (shipped in v2.1.0 but never consumed by UI until
  now) and shows uptime, total requests, error rate (red when > 1%),
  and the slowest endpoint's p95 latency.

### Added

- **Group-by toggle** with options None / 🏢 Company / 📁 Category.
  Preference persists in `localStorage` (`fp_overview_group`).
  Empty groups don't render; "Other" bucket only appears when at
  least one project is untagged.

- **Hub metrics strip** with four tiles:
    • Uptime in compact format (`1d 4h` / `23m` / `47s`)
    • Total requests (locale-formatted)
    • Error rate % with "N 5xx" raw count, red tint when > 1%
    • Slowest p95 ms + route name (backend sorts routes by p95 desc
      so `routes[0]` is always the worst)
  Loaded in parallel with project rollups via `Promise.allSettled` —
  a missing `/api/metrics` endpoint (older Hub) doesn't block the
  Health Matrix from rendering.

### Test coverage / build

- 11 Playwright e2e — all green (no regression).
- 125 pytest — unchanged (UI-only).
- Build: **313 KB JS / 106 KB CSS** (+3 KB JS, +2 KB CSS for the new
  metrics strip + group-block components).

## [2.2.0] — 2026-04-28

### Highlights

User-driven feature day after v2.1.0 — Project taxonomy navigation.
For users with 10+ projects, name + phase alone aren't enough to find
the right one quickly; this release adds Company / Category as
first-class filter axes in two places.

### Added

- **Topbar ProjectSwitcher**: native `<select>` replaced with a custom
  dropdown panel that supports
    • type-ahead search across name / id / company / category
    • filter chips per unique Company present in the project list
    • filter chips per unique Category
    • single-active filter dot on the trigger button when filter is on
    • selection mark (✓) on the currently-active project
    • "Showing N of M" footer + Clear-all
  Filter selections persist in `localStorage` (`fp_switcher_company`,
  `fp_switcher_category`) so a user with the Company set to "Acme"
  keeps that scope across refreshes.
  Apple-style: slide-down + scale-in animation (160ms ease), click-
  outside / Esc / Enter handling, theme-token colors throughout.

- **"Other" bucket** for projects with no Company / Category set.
  Renders as an italic ◌ Other chip (Topbar) and a "◌ Other (no
  company)" option (Projects tab dropdown). The chip / option only
  appears when at least one project in the dataset is actually
  untagged — fully-tagged datasets stay visually clean.

- **Projects tab filter bar** gains parallel dropdowns for Company
  and Category alongside the existing Phase / Type filters. Same
  `__none__` sentinel pattern as the Topbar.

### Test coverage / build

- 11 Playwright e2e — all green (no regression).
- 125 pytest — unchanged (this release is UI-only).
- Build: **310 KB JS / 104 KB CSS** (+7 KB JS, +5 KB CSS for the new
  ProjectSwitcher component and dropdown logic).

## [2.1.0] — 2026-04-28

### Highlights

Sprint D — ship-quality follow-up to v2.0.0. Five regression-prevention
items focused on stopping the audit's bug classes from coming back.

- **18 new tests pin every API contract** v2 reads — JSON shape
  snapshots that fail CI when a backend field is renamed.
- **Backend schema validation** turns silent field drops (the bug
  pattern that hid description/assignee for who-knows-how-long) into
  loud 400 errors with the offending key in the message.
- **`/api/metrics`** for production observability — per-route count,
  p50/p95/p99 latency, error rate. v2.0.0 is now in production so we
  start measuring it.

### Added

- **A1 — API contract tests** (`tests/test_api_contracts.py`).
  Pins JSON shape of `/api/projects`, `/api/info`, `/api/bugs`,
  `/api/release-gate`, `/api/flakiness`, `/api/status`, `/api/audit`,
  `/api/schedules`, all `/api/config/*`, `/api/validate/excel`, and
  `/api/metrics`. Two regression-guard tests for the silent-data-loss
  bugs round-trip `description` + `assignee` and assert that
  `/api/bugs/add` honors the `status` field.
- **A2 — Backend schema validation** (`schemas.py`).
  30-line `validate_body(required=[…], allowed=[…])` decorator (no
  new dependency) wired onto `/api/bugs/update` and
  `/api/projects/update`. A typo'd field now returns 400 with the
  offending key in the error — silent drop is now loud.
- **B4 — MiniReleaseGate auto-refreshes** after a pipeline run completes.
  Watches `pipeline.state` so the gate re-evaluates on every running →
  success/failed transition.
- **C1 — `/api/metrics`** endpoint. Returns per-route count / errors /
  p50 / p95 / p99 / max latency, sorted by p95 desc. Tracks last 200
  latencies per route in-memory, capped at 100 unique routes.
  Lightweight (50 lines, no extra dependency).
- **A3 — Stylelint** with `color-no-hex` rule. Warning-mode baseline
  (153 existing literals tracked) so new hex literals surface in
  `npm run lint:css` without blocking the build.

### Test coverage

- 122 → **125 pytest** (3 new contract tests + 2 schema regression
  guards already counted in A1's 18 above; 1 originally skipped).
- 11 Playwright e2e — unchanged, all green.
- Build size: **303 KB JS / 99 KB CSS** (101/17 KB gzipped) — flat
  from v2.0.0 (Sprint D added one component watch + one endpoint).

## [2.0.0] — 2026-04-28

### Highlights

- **Tab-by-tab audit closed 80+ gaps** across every primary view in v2.
- **Five silent backend bugs** discovered during the audit and fixed —
  these were API whitelist drops (Bug Tracker `description`/`assignee`,
  Project `company`/`category`), a missing `/api/output/list` endpoint,
  and `/api/bugs/add` quietly forcing every new bug to `status: "Open"`.
- **One entire view (System Check) was broken** due to API contract
  drift (`{check, status:"ok"}` vs `{step, ok:bool}`) — restored.
- **Test suite stayed green throughout**: 107 pytest + 11 Playwright e2e
  tests pass on every commit.

### Sprint C — feature additions

- **Sprint C Part 1** — Bug Kanban view + Screenshot evidence picker.
  Drag-drop bug status across Open/Fixed/Closed columns, with a
  click-to-cycle fallback for mobile. New ScreenshotPicker modal lets
  users insert markdown image snippets into bug descriptions.
- **Sprint C Part 2** — Pipeline Tools card with Debug Mode (`--headed
  --debug`), Excel TCM validation (filled %, screenshot coverage %,
  status pill breakdown), and Retrofit TCM for playwright-only projects.
- **Sprint C Part 3** — Per-stage file list (expandable [▸ N] badge on
  each pipeline stage) and Config Backup tab in Settings (Export/Import
  `config.json`).

### Audit — bug fixes by tab

#### Dashboard
- StatsRow Pass / Fail / Pass-rate / Screenshots all showed `—`. The
  `/api/info` endpoint returns counts as `totals.pass / totals.fail`
  (nested) for full-pipeline projects and `pw_last.pct` (not
  `pass_pct`) for playwright-only — frontend was reading flat
  `info.pass / info.fail / pw_last.pass_pct` which never existed.

#### Pipeline
- Log box rendered phantom blank lines top and bottom — `<pre>` with
  `white-space: pre-wrap` was preserving template indentation. Switched
  to `<div class="log-line">` per line with `min-height: 1em`.
- Mode bar showed three buttons regardless of project type. For
  `playwright-only` only Stage 5 ran anyway, and for `manual-testing`
  the "Full" / "Manual TCM" options collapsed to the same pipeline.
  Now `availableModes` derives from `currentMeta.type` and the bar
  hides itself when there's nothing to choose.
- `runAll()` / `retrofitTcm()` used native `window.confirm()` — replaced
  with `useConfirm` modal to match the rest of v2.
- `useSSE`'s clean-close detection used `readyState === CLOSED` which
  is unreliable (EventSource auto-reconnects). On real network drops
  the UI silently froze. Now disambiguates via the Flask `{done: true}`
  sentinel and pushes a synthetic error line into the log so the
  failure is visible and downstream `onClose` handlers correctly mark
  the pipeline as failed.

#### Release Readiness
- `verdict` has 5 distinct values (`GO / NOGO / NOT_READY /
  SKIP_PLANNING / SKIP_PAUSED`) but the UI collapsed everything to
  `go: bool`. A planning-phase project showed up as red NOGO.
- Failed criteria gave no actionable next step. Each criterion id now
  deeplinks to where you fix it (`tcm_uploaded` → `/input`,
  `pass_rate` → `/pipeline`, `no_critical_bug` → `/bugs`, …).
- Added top-level CTA based on verdict (Send Report / Fix first issue /
  Run tests), 📋 Copy as Markdown for release notes, project meta
  header, and a "current vs target %" overlay on threshold tiles.

#### Schedule
- Tag convention drift: Pipeline UI stored `"smoke"` (server prepends
  `@`), Schedule UI stored `"@smoke"` verbatim. Both worked but ran on
  inconsistent paths. Normalized — Schedule now stores without `@`,
  scheduler prepends, and tolerates legacy entries.
- Added next-run preview ("⏱ in 4h 25m"), filter by status / project,
  Enter-to-add for recipients, useConfirm modal for delete / run-now /
  prod-risky add, and post-add form reset (preserving `project_id`).

#### Bug Tracker
- **Backend silent data loss**: `/api/bugs/update` whitelist did not
  include `description` or `assignee`. BugEditModal and BugAssignModal
  showed "Bug updated" success while values were silently dropped.
  Both fields added to the whitelist.
- **Backend silent default**: `/api/bugs/add` ignored the `status`
  field and always set `Open`. Fixed by validating + persisting the
  caller's value.
- Added free-text search (title + description + assignee), status
  filter (Open/Fixed/Closed/All, default Open), assignee filter,
  inline severity select for symmetry with status, 📝 desc indicator
  on rows, "Add description" textarea in the add card, severity-tinted
  stat tiles showing `open / total`.

#### Activity Feed
- Object detail values rendered as `[object Object]`.
  `stringifyDetail()` now JSON.stringify's non-primitives.
- Action color used substring matching (`action.includes('remove')`)
  which would falsely red-tag any future `*_pending`-style action.
  Replaced with `actionCategory()` regex on the verb segment.
- Added free-text search across action / user / ip / details, relative
  time ("3m ago" with full-ts hover), smart day labels (Today /
  Yesterday / "Mon, 28 Apr"), and a 📋 Copy-as-JSON button per row.

#### All Projects Overview
- Same `verdict` collapse bug as Release Gate — fixed.
- Added shimmer skeleton for first load, refresh button + last-loaded
  timestamp, clickable rows that call `projects.select()` then push
  `/dashboard`, search box + phase filter (Active / Planning / Paused).
- Summary tiles now exclude paused/planning projects from the
  broken/flaky count via `isActive()`.

#### Projects
- Cards ignored ~70% of the `/api/projects` payload. Server returns
  `exists / has_xlsx / has_docx / screenshot_count / last_run /
  company / category` — UI rendered only `id` and `path`. New status
  pills (📋 TCM · 📄 Report · 📷 N · ⏱ last_run) and taxonomy chips
  (🏢 company / 📁 category).
- Folder existence wasn't visualised — a project whose folder was
  deleted on disk looked healthy, then Pipeline crashed. Cards with
  `exists: false` now flash danger styling, disable Select, sort
  to top, and explain why.
- "Select" button was a dead-end (set the store, leave you on
  Projects). Now "Select & Open →" navigates to `/dashboard`.
- **Backend silent drop**: `/api/projects/update` whitelist did not
  include `company` / `category`. Refactored to a loop over optional
  string fields where empty string deletes the key.
- Quick Add for an Auto-Discover hit now dedupes against existing
  project ids client-side (greys out and disables the row).

#### System Check
- **Entire view was broken** by API contract drift. Backend SSE emits
  `{check, status: "ok"|"fail", detail}` per step and `{done, passed,
  total}` for summary. Frontend expected `{step, ok: bool, detail}` and
  `{done, summary: {passed, failed}}`. Result: every row rendered
  yellow-pending with no title; the summary banner never appeared.
  Effectively unusable since the last backend refactor.
- Added Stop button, ticking elapsed time, n/8 progress counter, full
  plan checklist rendered up-front, error banner that surfaces the
  synthetic SSE error line, and 📋 Copy as Markdown.

#### User Guide
- Shortcut table only listed 6 of the 14 keyboard shortcuts the code
  actually wires up. Documented the full set, split into Global /
  Navigation, noted the 1.2-second sequence window.
- Anchor links scrolled section headings under the 64px topbar +
  sticky quick-nav. Added `scroll-margin-top: 130px` per `.card[id]`.
- External Gmail App Password link missing `rel="noopener noreferrer"`.
- Several callout / verdict-pill text colors had no dark-mode overrides.
- Added a Feedback section pointing to GitHub issues + the per-project
  `logs/feedback.md`, with explicit "paste your System Check report
  (📋 Copy)" guidance.

#### Settings (5 sub-tabs)
- Tab nav, Branding, Email, Notifications, AI — all migrated from
  hex-hard-coded colors to theme tokens (`--primary`, `--muted`,
  `--success-soft`, …) so dark mode renders correctly throughout.
- Branding `reset()` now uses `useConfirm`; live-preview text moved
  into scoped classes that respect dark mode.
- Email: 👁 Show/Hide buttons on SMTP password and Resend API key,
  duplicate-email rejection, email-shape regex check, Enter-to-Add on
  recipient inputs, `noopener` on the resend.com link, "Test uses
  current form values" hint inline.
- Notifications: same theme-token treatment for the Test buttons; hint
  clarifies that Test sends to whichever URL is in the field right now.
- AI: 👁 Show/Hide on the API key field; success-tinted "key saved"
  indicator with dark-mode override; divider extracted from inline
  hex to a `.divider` class.

#### Input / Output
- Both tabs showed blank Size and Modified columns. Two distinct
  bugs:
  1. Field-name mismatch — API returns `{size_kb, modified, ext}`
     but frontend read `{size, mtime}`. `fmtSize()` also assumed bytes
     where the API sends KB.
  2. **`/api/output/list` never existed** — only `/api/output/download`.
     Output tab silently 404'd → empty file list. Endpoint added,
     mirroring the input/list pattern; `/api/output/download` extended
     to accept `?f=<name>` for picking a specific file (with path-
     traversal guard).

#### Screenshots
- **Bug**: thumbnails returned 404 for every image. Frontend built
  `/api/screenshots/file?p=…&f=…` but the Flask route is
  `/api/screenshots/<path:filepath>?p=…` (path param, not query).
  Resolved to `filepath="file"` server-side, hence 404 universally.
- Added Grid / Compact / List view modes (persisted in localStorage),
  search by TC ID or filename, optional "Group by date" with smart
  buckets (Today / Yesterday / 7 days / older).

### Recurring patterns fixed across multiple tabs

Several anti-patterns surfaced in nearly every view and were
straightened out to a single design-system convention as the audit
progressed:

- **Hex hard-coding** in CSS broke dark mode in 11 of 14 views —
  migrated to theme tokens with `[data-theme="dark"]` overrides for
  tinted text.
- **Native `window.confirm()`** in 5+ places — replaced with the
  promise-based `useConfirm` modal.
- **Empty states** that didn't distinguish "no data ever" from
  "current filter excluded everything" — split into two clear states
  with a "Clear filters" affordance on the latter.
- **Filter / sort / search** missing on list views with 20+ rows —
  added segmented controls or text inputs as appropriate.
- **External links** without `rel="noopener noreferrer"` —
  fixed throughout.
- **No skeleton loaders** on initial fetch — added shimmer skeletons
  that match the real layout so pages don't reflow when data arrives.

### Test coverage

- 107 pytest unit + integration tests (audit, validators, flakiness,
  notifications, AI provider, integration flow, ...)
- 11 Playwright e2e smoke tests covering every nav route, settings
  sub-tabs, real-API plumbing for Bug Tracker and Overview, and the
  legacy dashboard parity guard.
- Build size after audit: **303 KB JS / 99 KB CSS** (101 KB / 17 KB
  gzipped) — up from ~258 KB / 66 KB at the start of Sprint C.

[Unreleased]: https://github.com/ArtSadVoice/qa-hub-saucedemo/compare/v2.12.0...HEAD
[2.12.0]: https://github.com/ArtSadVoice/qa-hub-saucedemo/compare/v2.11.0...v2.12.0
[2.11.0]: https://github.com/ArtSadVoice/qa-hub-saucedemo/compare/v2.10.0...v2.11.0
[2.10.0]: https://github.com/ArtSadVoice/qa-hub-saucedemo/compare/v2.9.0...v2.10.0
[2.9.0]: https://github.com/ArtSadVoice/qa-hub-saucedemo/compare/v2.8.0...v2.9.0
[2.8.0]: https://github.com/ArtSadVoice/qa-hub-saucedemo/compare/v2.7.0...v2.8.0
[2.7.0]: https://github.com/ArtSadVoice/qa-hub-saucedemo/compare/v2.6.0...v2.7.0
[2.6.0]: https://github.com/ArtSadVoice/qa-hub-saucedemo/compare/v2.5.0...v2.6.0
[2.5.0]: https://github.com/ArtSadVoice/qa-hub-saucedemo/compare/v2.4.0...v2.5.0
[2.4.0]: https://github.com/ArtSadVoice/qa-hub-saucedemo/compare/v2.3.0...v2.4.0
[2.3.0]: https://github.com/ArtSadVoice/qa-hub-saucedemo/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/ArtSadVoice/qa-hub-saucedemo/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/ArtSadVoice/qa-hub-saucedemo/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/ArtSadVoice/qa-hub-saucedemo/releases/tag/v2.0.0
