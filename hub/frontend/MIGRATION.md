# Vue v2 Migration Roadmap

A living checklist for the strangler migration. Update as tabs move from
vanilla → Vue. Estimates assume one focused half-day per non-trivial tab.

## Status legend

- ✅ done in Vue, available at `/v2/<route>`
- 🟡 PoC quality — works but missing features/parity
- ❌ not started — still served by legacy `/`
- — not applicable / no equivalent

## Phase 2 — New features only (Vue-first, no legacy churn) · COMPLETE

| Feature | Status | Route | Notes |
|---|---|---|---|
| App shell (sidebar + topbar + project switcher) | ✅ | — | Pinia `useProjectStore` shared with legacy via `localStorage('fp_project')` |
| Dashboard — health snapshot | ✅ | `/v2/dashboard` | Pulls `/api/hub/health` |
| Bug Tracker | ✅ | `/v2/bugs` | full parity — add/edit/delete + sortable columns + aging indicator + assignee |
| Activity Feed (NEW — no vanilla equivalent) | ✅ | `/v2/activity` | Groups `/api/audit` by day |
| All Projects Overview (NEW — richer than legacy summary) | ✅ | `/v2/overview` | Combines flakiness + bugs + release-gate per project |

## Phase 3 — Strategic migration (one tab at a time) · IN PROGRESS

Order chosen by **(impact × isolation)**: tabs with few legacy entanglements first,
high-traffic tabs last.

| Tab | Legacy section | Status | Notes |
|---|---|---|---|
| Bug Tracker | `bugs` | ✅ ready to flip | edit modal + sortable columns + aging |
| Schedule | `schedule` | ✅ ready to flip | full CRUD + per-schedule notify_on + Prod warning |
| All Projects Summary | `summary` | ✅ replaced by Overview | richer cross-project view in v2 |
| Release Readiness | `release` | ✅ ready to flip | verdict banner + criteria list + thresholds |
| Projects | `projects` | 🟡 partial parity | list/edit/remove + register-folder; scaffold/git uses legacy |
| About → Branding | `about` | ✅ ready to flip | form + live preview + reset |
| About → Email Settings | `about` | ✅ ready to flip | SMTP/Resend toggle + recipients + Test |
| About → Notifications | `about` | ✅ ready to flip | 3 webhooks + per-service Test |
| About → AI Settings | `about` | ✅ ready to flip | provider switch + key-preserve + generator |
| About → Audit Log | `about` | ✅ replaced by Activity Feed | richer day-grouped view |
| About → Hub Health | `about` | ✅ replaced by Dashboard | live refresh |
| About → Email Template | `about` | ❌ deferred | Jinja2 editor — kept on legacy until needed |
| Pipeline (stages 1-9) | `pipeline` | ✅ ready to flip | stage list + SSE log + tag/env selectors + cancel |
| Input | `input` | ✅ ready to flip | shared FilesView component |
| Output | `output` | ✅ ready to flip | shared FilesView + download links |
| Screenshots | `screenshots` | ✅ ready to flip | grid + lightbox + download-all |
| Chart | `chart` | — | low value as standalone tab; use Dashboard chart |
| User Guide | `guide` | ✅ ready to flip | rewritten for v2 |
| System Check | `syscheck` | ✅ ready to flip | SSE stream + per-check status + summary |

**Phase 3 substantially complete** — 18 of 19 listed items ready-to-flip,
1 deferred (Email Template), 1 dropped (Chart standalone). See
`PRODUCTION.md` for the deployment + sunset checklist.

## Phase 4 — Continue migration (3-6 months, organic) · NOT STARTED

Strategy: don't force a calendar. Migrate a tab when:

1. You're already touching it for a feature/bug fix → migrate before merging
2. The legacy version has a bug Vue would solve naturally (state sync, etc.)
3. Quarterly review reveals a tab that hasn't been touched in 6+ months — leave it

Triggers to **stop migrating** and stay hybrid forever:
- Pipeline tab (huge, SSE-heavy) refuses to fit cleanly in Vue
- A teammate's preference is split — keep both running indefinitely

## Phase 5 — Sunset legacy · NOT STARTED

Only when all Phase 3 tabs are done in Vue:

- [ ] Vue covers 100 % of features
- [ ] All e2e tests pass against `/v2/` routes
- [ ] No bugs filed against Vue tabs in last 30 days
- [ ] Switch `/` route to redirect to `/v2/`
- [ ] Delete `templates/dashboard.html`, `static/app.js`, `static/app.css`
- [ ] Update `CLAUDE.md` architecture diagram to remove vanilla layer
- [ ] Final commit message: `refactor(hub): sunset vanilla dashboard — Vue v2 is now canonical`

## Stop conditions (any of these = stay hybrid)

- Vue migration takes 5x the estimated time
- Vue introduces > 5 production bugs in a month
- A team decides they prefer the legacy UI for any tab
- Maintenance burden (npm updates, vue-router upgrades) exceeds the value

## Conventions for new Vue work

1. Every API call goes through `apiCall()` from `@/api/client` — no raw fetch
2. Every shared piece of state goes in a Pinia store under `src/stores/`
3. Component-scoped styles in SFC `<style scoped>`; only true globals in `src/styles/app.css`
4. Match legacy URL patterns where possible: `/v2/bugs` mirrors `?section=bugs`
5. New features are Vue-only by default — don't add to legacy unless the user explicitly requests it

## Quick reference

```bash
# Dev
cd frontend && npm run dev          # http://localhost:5173 with HMR

# Build (CI does this on every push too)
cd frontend && npm run build         # output → ../static/dist/

# Type-check only (fast — runs in vue-tsc)
cd frontend && npm run type-check

# Add a new view
1. Create src/views/MyTabView.vue
2. Register in src/router/index.ts
3. Add nav entry in src/components/Layout/Sidebar.vue
```
