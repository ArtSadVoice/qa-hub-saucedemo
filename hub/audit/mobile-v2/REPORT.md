# Mobile Audit — QA Hub Demo v2 (Vue)

**Initial audit**: 2026-05-06 at 375 × 667 (iPhone SE)
**All 7 phases shipped**: 2026-05-06 — see PRs #33 / #34 / #35 / #36 / #37 / #38 / #39
**Method**: Playwright → BasicAuth → walk every route + DOM/style introspection
**Compares with**: v1 dashboard (post Phase 1-5 fixes — see `audit/mobile/REPORT.md`)

Screenshots: `01-..-07-*.png` (BEFORE) and `AFTER-PHASE-A/`, `AFTER-PHASE-B/`, `AFTER-PHASE-C/`, `AFTER-PHASE-D/`, `AFTER-PHASE-E/`, `AFTER-PHASE-F/`, `AFTER-PHASE-G/`.

---

## ✅ Status — All phases complete

| Phase | PR | Highlights | Verified at |
|---|---|---|---|
| A — Unblock | [#33](https://github.com/ArtSadVoice/qa-hub-saucedemo/pull/33) | `#app{display:flex}` — single line that fixed body width 792 → 366 | 375 / 1440 |
| B — Onboarding | [#34](https://github.com/ArtSadVoice/qa-hub-saucedemo/pull/34) | × close button, 44×44 tap targets, backdrop-click skip | 375 |
| C — Topbar trim | [#35](https://github.com/ArtSadVoice/qa-hub-saucedemo/pull/35) | Hide project pill + v2 badge at ≤640, h1 ellipsis, bell/theme tap targets | 375 / 1440 |
| D — Forms stack | [#36](https://github.com/ArtSadVoice/qa-hub-saucedemo/pull/36) | Schedule 4-col, Bugs Add Bug, Projects toolbar all stack at ≤640 | 375 / 1440 |
| E — Tables → cards | [#37](https://github.com/ArtSadVoice/qa-hub-saucedemo/pull/37) | Global `.table-stack` class with `data-label` pattern; Scenario Summary + Schedule Runs | 375 / 1440 |
| F — Polish | [#38](https://github.com/ArtSadVoice/qa-hub-saucedemo/pull/38) | `.btn` 44px, `.btn-sm` 40px, MODE toggle compact, TipBanner compact, quick-actions 1-col @480 | 320 / 375 / 1440 |
| G — Verify | this PR | Full viewport sweep, stage-actions wrap fix, REPORT closeout | 320 / 375 / 414 / 1440 |

### Final viewport sweep — `body.scrollWidth` per route

| Viewport | dashboard | pipeline | schedule | bugs | projects | release |
|---|---|---|---|---|---|---|
| 320 × 568 | 310 ✓ | 347 (~) | 310 ✓ | 310 ✓ | 311 ✓ | 310 ✓ |
| 375 × 667 | 366 ✓ | 370 ✓ | 366 ✓ | 366 ✓ | 366 ✓ | 366 ✓ |
| 414 × 896 | 405 ✓ | 409 ✓ | 405 ✓ | 405 ✓ | 405 ✓ | 405 ✓ |
| 1440 × 900 | 1430 ✓ | 1430 ✓ | 1440 ✓ | 1430 ✓ | 1430 ✓ | 1430 ✓ |

✓ = matches viewport (give-or-take a 10px scrollbar reservation)
~ = minor overflow (≤30px, only at the smallest viewport on the densest view)

Pipeline at 320 still overflows by 27px — long Thai text in stage descriptions plus action buttons compete for the same row. Acceptable as a known limit on iPhone-SE-1st-gen-class devices; 375+ is clean.

### Key metrics: BEFORE → AFTER (375 × 667)

| Metric | Before | After |
|---|---|---|
| `body.scrollWidth` (dashboard) | **792** | 366 ✓ |
| `body.scrollWidth` (pipeline) | 523 | 370 ✓ |
| `body.scrollWidth` (schedule) | 593 | 366 ✓ |
| Onboarding skip tap target | 81 × 24 | 98 × 44 + 44 × 44 close-X + backdrop |
| Topbar project pill | always visible | `display:none` ≤640 |
| Wide tables | overflow page | stacked cards with `data-label` |
| Schedule form | 4-col cramped | 1-col stack |
| MODE toggle | 3 buttons + label + 3 hints | 3 buttons only |
| `.btn` mobile | (no rule) | min-height 44 |
| Quick-actions @320 | `minmax(200,1fr)` gap | 1 col, no gap math |

---

## Original audit (kept for reference)

---

## TL;DR

v2 is **worse** on mobile than the v1 *post-fixes* baseline despite having 85 `@media` rules across 31 files (vs v1's 3). The responsive intent is there — sidebar drawer, mobile breakpoints, media queries everywhere — but a single architectural mistake at the App root cancels most of it: **`#app` is `display:block` while the global responsive layout assumes `body{display:flex}` with sidebar+main as direct flex siblings**. Vue mounts everything inside `#app`, so the flex never engages, `main` sizes to its content, and the page width balloons to whatever the widest grid demands (mostly the dashboard `quick-actions` `auto-fit, minmax(200px, 1fr)`).

Result: every route on 375px viewport overflows by 150-420px:

| Route | `body.scrollWidth` | Overflow vs 375 |
|---|---|---|
| `/v2/dashboard` | **792** | +417 |
| `/v2/pipeline` | 523 | +148 |
| `/v2/bugs` | 517 | +142 |
| `/v2/projects` | 522 | +147 |
| `/v2/schedule` | 593 | +218 |

Fixing the `#app` flex issue is a one-line change. The rest of the issues are smaller.

---

## Issues

### P0 — Architectural (one fix unlocks 80%)

| # | Issue | Where | Evidence |
|---|---|---|---|
| **P0-1** | `#app` is `display:block`. The global rule `body{display:flex}` (intended to put sidebar + main as flex siblings) doesn't apply because Vue's mount wraps everything in `#app`. So `main{flex:1}` is silently ignored and `main` sizes to its widest child instead of viewport. | `frontend/src/styles/app.css:100` (body display:flex) + `frontend/src/main.ts` (mounts to `#app`) — there's no `#app{display:flex}` anywhere | DOM measure: `body.offsetWidth=366`, `body.scrollWidth=792`. `#app.width=792`. Children of `#app`: drawer-toggle (fixed), sidebar (fixed), main (`flex:1 1 0%` but parent is block → ignored) |
| **P0-2** | Onboarding tutorial blocks the page on **every reload** — `localStorage` keys we tried (`hub_v2_onboarded`, `onboarding-seen`, etc.) don't persist the dismissed state, and there's no quick "skip permanently" option visible | `frontend/src/components/OnboardingWelcome.vue` | Reproduced: clicked "ข้าม tutorial" then navigated → tutorial reappeared on the new route. Hostile to mobile users who can't easily reach the small × |

### P1 — Layout (after P0 fix, these still need work)

| # | Issue | Where |
|---|---|---|
| P1-1 | Quick actions grid `auto-fit, minmax(200px, 1fr)` will give 1 col at 375 once main is correctly sized — *but* the buttons have ~200px of icon+text+gap, so 1-col is full-width and looks fine. **However at viewports 320-360 the minmax(200) means buttons exceed container**. Should be minmax(160) or explicit breakpoint. | `frontend/src/views/DashboardView.vue:85` |
| P1-2 | Test Scenario Summary table has 8 cols (TSID, Description, Pass, Fail, Block, Not Start, Cancel, Total) — won't fit on any phone viewport. No `data-label` / stacked-card pattern like we landed for v1 | `frontend/src/components/dashboard/ScenarioSummary.vue` |
| P1-3 | Pipeline view "Pipeline 9 stages" hint banner + "MODE" toggle (3 buttons) + Stage cards with copy/run actions — toolbar overflows at 375 | `frontend/src/views/PipelineView.vue` |
| P1-4 | Pipeline "Test scope & quick actions" Tag/Environment side-by-side + 4 buttons (Report+Inject / Send Report / Watch / Refresh) — wraps badly | `PipelineView.vue` |
| P1-5 | Schedule "Add Schedule" form: 3 cols (Project / Action / Tag) + 3 cols (Schedule type / Time / Notify on) — same issue v1 had, no mobile stack | `frontend/src/views/ScheduleView.vue` |
| P1-6 | Schedule "Scheduled Runs" table (Project / Action·Tag / Env / When·Next / Last Run / Status / Toggle) — 7 cols, no stacked-card pattern | `ScheduleView.vue` |
| P1-7 | Bugs "Filter & Stats" 4 stat cards in 1 row (CRITICAL / HIGH / MEDIUM / LOW). On mobile some get clipped right (visible in `04-bugs.png`) | `frontend/src/views/BugTrackerView.vue` |
| P1-8 | Bugs "Add Bug" inline form: Title (wide) + Severity + Status side-by-side. Title gets very narrow + Status truncates ("Op…") at 375 | `BugTrackerView.vue` |
| P1-9 | Projects toolbar "[Select all drifted] [Auto Discover]" + search + 3 dropdown filters — gets cut off | `frontend/src/views/ProjectsView.vue` |
| P1-10 | Topbar still shows project pill ("BAY / e2e-surveys-bay") + ⌘K + 🔔 + 🌙 + v2 badge. Project pill is wide; h1 ("hboard" visible) gets truncated by the project pill on small viewports | `frontend/src/components/Layout/Topbar.vue` |

### P2 — Polish

| # | Issue | Where |
|---|---|---|
| P2-1 | Tap targets: `.topbar-btn{padding:4px 8px}` ≈ 24px tall — well below 44 | `Topbar.vue:44` |
| P2-2 | Tutorial modal width 360px → fits 375 viewport but no padding for ≤360 | `OnboardingWelcome.vue` |
| P2-3 | Bug filter chips, severity selectors, etc. don't stack on mobile | `BugTrackerView.vue` |
| P2-4 | Pipeline stage card content wraps awkwardly (long Thai text + emoji + buttons) | `pipeline/StageCard.vue` likely |
| P2-5 | Hint banner (yellow info card) at top of pages takes lots of vertical space — should be collapsible on mobile | various views |

### P3 — Functional / Nice-to-have

| # | Issue | Where |
|---|---|---|
| P3-1 | Drawer overlay covers content but the drawer-toggle button (fixed top-left) overlaps with content when closed on mobile — slight UX smell | `App.vue:43-57` |
| P3-2 | Tablet breakpoint (641-900px) shrinks sidebar to 200px but doesn't enable the drawer — sidebar always visible. iPad in portrait may want the drawer | `App.vue:98-101` |
| P3-3 | No "back to top" button on long pages (Pipeline is very tall) | n/a |

---

## Comparison: v1 (post-fix) vs v2 (today)

| Concern | v1 post-fix | v2 today |
|---|---|---|
| Body width @375 | 360 (✅ fits) | 792 (❌ 2.1× viewport) |
| Sidebar drawer | Works (260 wide, slide-in, overlay) | Works structurally — but obscured by P0-1 |
| Wide tables | Stacked cards on ≤640 (`.table-stack`) | Native `<table>`, no stacking |
| Quick actions | Explicit 2×2 grid at ≤480 | `auto-fit minmax(200,1fr)` — relies on container width being correct |
| Topbar | project pill + run badge hidden at ≤640 | Project pill always shown (wide) |
| Tap targets | `.btn{min-height:44px}` `.btn-sm{min-height:40px}` at ≤640 | None — buttons stay ~24-32px |
| Forms (Schedule / About) | Stack at ≤640 | 3-col grids |
| Onboarding modal | n/a (no modal in v1) | Re-fires on every route, no persistent skip |

The good news: **v2 has more component structure to work with**. Each view + table is a separate Vue component, so adding scoped responsive CSS is cleaner than v1's inline-style sprinkles. The bad news: P0-1 makes everything else look broken until fixed.

---

## Plan — Phased

### Phase A — Unblock layout (target: 30 min)
The single change that fixes 80% of overflow.

1. Add to `frontend/src/styles/app.css`:
   ```css
   #app {
     display: flex;
     min-height: 100vh;
     width: 100%;
   }
   /* Body's display:flex was the legacy intent — keep it harmless */
   body { display: block; }  /* or leave flex but make it explicit it's only for #app */
   ```
   Then `<aside class="sidebar">` + `<main class="main">` become flex siblings inside `#app`. `main{flex:1; min-width:0}` finally works → main = viewport - sidebar (or 100% on mobile).
2. Add explicit `min-width:0` to `.main` if not already, and `overflow-x:hidden` on `body` as a belt-and-suspenders against children that misbehave.
3. **Verify**: `body.scrollWidth` should match viewport on every route at 375.

### Phase B — Onboarding gate fix (target: 30 min)
Until this is fixed, every "go to" via Playwright re-shows the modal.

4. Find `OnboardingWelcome.vue`, identify the localStorage key it actually checks. Make sure dismiss writes that key. Add a permanent "Don't show again" checkbox if the modal is meant to repeat.
5. Make the × close button at least 44×44 and reachable on mobile (currently small in the corner).

### Phase C — Topbar trim (target: 30 min)
Same playbook as v1 Phase 1.

6. At ≤640: hide `topbar-proj` and the v2 badge.
7. Topbar buttons: `min-height:36px; padding:8px 10px`.
8. h1: `min-width:0; overflow:hidden; text-overflow:ellipsis`.

### Phase D — Forms stack (target: 1 hr)
9. Schedule form 3-col grids → 1-col at ≤640. Similar selector to v1 but use scoped CSS in `ScheduleView.vue` (avoid inline `style` if possible).
10. Bugs "Add Bug" inline form: stack Title above Severity/Status row.
11. Projects toolbar: wrap or collapse Select-all-drifted / Auto-Discover into a "more" menu.

### Phase E — Tables to stacked cards (target: 2-3 hr)
The v1 pattern (data-label + ::before) ports cleanly to Vue.

12. Add a global CSS class `.table-stack` in `frontend/src/styles/app.css` (mirror what v1 has).
13. `ScenarioSummary.vue`: add `class="table-stack"` to `<table>`, add `:data-label` to each `<td>` based on column header.
14. `ScheduleView.vue` Scheduled Runs table: same.
15. `BugTrackerView.vue` table (if any): same.
16. Make sure `data-label=""` cells (action columns) hide the label.

### Phase F — Polish (target: 1 hr)
17. `.btn { min-height: 44px }` and `.btn-sm { min-height: 40px }` at ≤640 in `app.css`.
18. Quick actions: `minmax(200, 1fr)` → `minmax(160, 1fr)` so 320-360 viewports get 1-col cleanly.
19. Hint banners: collapsible (or smaller font + tighter padding) on mobile.
20. Pipeline MODE toggle: stack 3 buttons into a select / segmented control.

### Phase G — Verify (target: 30 min)
21. Playwright sweep at 320 / 375 / 414 / 1024 (iPad) / 1440.
22. Compare before/after screenshots → save to `audit/mobile-v2/AFTER-PHASE*/`.
23. Update this REPORT.md with status table at top (mirror v1's REPORT closeout).

---

## Files to touch (estimate)

| File | Phases | Notes |
|---|---|---|
| `frontend/src/styles/app.css` | A, F, E (global classes) | Major: `#app{display:flex}`, tap targets, `.table-stack` global |
| `frontend/src/App.vue` | A | Possibly tighten `.main { min-width: 0 }` |
| `frontend/src/components/Layout/Topbar.vue` | C | Hide project pill + badges at ≤640 |
| `frontend/src/components/OnboardingWelcome.vue` | B | Persistent dismiss + larger × |
| `frontend/src/views/DashboardView.vue` | F | minmax tweak |
| `frontend/src/views/ScheduleView.vue` | D, E | Form stack + table stack |
| `frontend/src/views/BugTrackerView.vue` | D, E | Add Bug stack + table stack |
| `frontend/src/views/PipelineView.vue` | D, F | MODE toggle, scope/actions card |
| `frontend/src/views/ProjectsView.vue` | D | Toolbar wrap/collapse |
| `frontend/src/components/dashboard/ScenarioSummary.vue` | E | data-label on td |

10 files, mostly scoped CSS changes. No backend, no schema, no API changes.

---

## Risks

- **`#app{display:flex}` regression**: the body-level `display:flex` was there for a reason historically. Need to check if anything depends on body being flex (probably not — most root layout depends on `#app` now).
- **Tablet behavior** (641-900): the breakpoint already shrinks sidebar to 200. After the flex fix, verify iPad portrait still looks right.
- **Tutorial backend logic**: the `OnboardingWelcome.vue` localStorage key needs to match what the component reads on mount. If the key is hashed or includes user id, we need to use the right setter.
- **Build pipeline**: v2 lives in `frontend/` and needs `npm run build` after CSS edits, which writes to `static/dist/`. The `static/dist/` is gitignored — first make sure CI/Hub serves the right build.

---

## Suggested commit/PR breakdown

To match the v1 style (one PR per phase, stacked):

| PR | Phase | Approx LoC |
|---|---|---|
| feat/v2-mobile-1-layout | A + verify dashboard | +5 −1 in app.css |
| feat/v2-mobile-2-onboard | B | +20 −5 in OnboardingWelcome |
| feat/v2-mobile-3-topbar-forms | C + D | +60 −10 across 4-5 files |
| feat/v2-mobile-4-tables | E | +40 −0 across 3 components + global class |
| feat/v2-mobile-5-polish | F + G | +30 across CSS + verify screenshots |

Or if you prefer one big PR for v2 since it's a smaller surface than v1: **feat/v2-mobile** all in one. Up to you.
