# Demo script — QA Hub for saucedemo.com

Live walkthrough script (~12-15 minutes), tuned for **QA Engineer /
Test Automation interviews**. Slides at `docs/SLIDES.html`. Repo:
<https://github.com/ArtSadVoice/qa-hub-saucedemo>.

> **Tone tip:** speak in plain language. Slides cover *what* — your
> job in the live demo is the *why*. One sentence per point, then click.
> Lean into **test design decisions, coverage rationale, evidence-
> based release verdicts** — those are the QA signals interviewers
> listen for.

---

## 0. Setup before the call (2 min, off-camera)

```powershell
cd C:\Automation\qa-hub-saucedemo
./setup.ps1                              # installs deps + seeds data + starts hub
# Hub now running at http://localhost:8080
```

Open four browser tabs in advance:

1. `docs/SLIDES.html` (slides — start here)
2. `http://localhost:8080` (hub dashboard)
3. `https://www.saucedemo.com/` (target site)
4. `projects/saucedemo/tests/pages/LoginPage.ts` (code reference)

---

## 1. Opening — 30 seconds

> **EN:** "Hi, I'm <Name>. I'd like to walk you through a portfolio
> project — a **Playwright TypeScript test suite** for saucedemo.com
> wrapped in a small **QA orchestration hub** that I built to
> demonstrate how I'd structure test automation for a small QA team."

> **TH:** "สวัสดีครับ ผมจะ walk through portfolio ผม &mdash; เป็น
> **Playwright TypeScript test suite** ทดสอบ saucedemo.com ครอบด้วย
> **QA hub** เล็กๆ เพื่อโชว์ว่า ถ้าผมต้องวาง test automation ให้
> ทีม QA ทีมเล็ก ผมจะวาง coverage, การจัดการ bug, และ
> release decision ยังไง"

➜ **Click slide 1**

---

## 2. The QA problem this solves — 1 minute

> "Most small QA teams I've seen run Playwright or pytest **locally**.
> Each engineer sees their own results. Bugs live in heads. When
> the team lead asks 'are we ready to ship?' &mdash; the answer is a
> feeling, not data.
>
> This hub turns that into evidence: **central run history,
> tag-based test scope, bug tracker that feeds the release gate,
> and an automated GO/NOGO verdict** based on six criteria."

➜ **Click slide 2 (Problem / Solution side-by-side)**

> **TH cue:** "ทำให้ 'ทีมพร้อม release รึยัง' เป็น **คำถามที่ตอบจาก
> data ไม่ใช่จาก feeling**"

---

## 3. Tech stack — 30 seconds (compressed)

➜ **Click slide 3**

> "Three things matter for QA: **Playwright TypeScript** for tests,
> **JSON state files** for run history + bugs + schedules, and a
> **release gate** that reads from both. The Flask/Vue dashboard is
> just the UI &mdash; I can talk about it if you're curious, but the
> real story is in the test design and the gate logic."

> **TH cue:** stack สำคัญ 3 ส่วน &mdash; tests, state, gate. UI
> เป็นแค่หน้าตา

(**Skip slide 4 architecture for QA interview** unless asked.
Most QA interviewers care about *what's tested* not *how it's wired*.)

---

## 4. Test design — 6 users = 6 scenarios — 1.5 minutes

➜ **Click slide 5 (saucedemo home)**

> "The system under test &mdash; saucedemo is a **live e-commerce
> demo** with six built-in test users. I picked it for portfolio
> work because each user is **a natural test scenario**, not a
> synthetic happy-path."

➜ **Click slide 6 (six users grid)**

> "**These six users *are* my test plan.** Look:
>
> - `standard_user` &mdash; happy path. Login, browse, cart, checkout,
>   logout. The baseline that has to work every release.
> - `locked_out_user` &mdash; assert the *exact* error copy. Catches
>   regressions in error UX.
> - `problem_user` &mdash; serves the same dog photo for every product.
>   Visual-bug regression target.
> - `performance_glitch_user` &mdash; slow login. Catches loading-state
>   bugs and timeouts.
> - `error_user` &mdash; form validation breaks. Catches checkout flow
>   regressions.
> - `visual_user` &mdash; subtle layout shifts. Pixel/structural diff."

> **TH cue:** "ผมไม่คิด test cases เอง แต่ใช้ **personas ที่ saucedemo
> ออกแบบไว้แล้ว** เป็น checklist &mdash; happy / locked / problem /
> glitch / error / visual ครอบคลุมทุก state ของ user journey"

---

## 5. Show the code — 1 minute

➜ **Click slide 7 (Page Object Model snippet)**

> "Page Object Model means **specs read like requirements, not code**.
>
> The `TEST_USERS` const documents saucedemo's six users in **one
> place**. Spec body is `await login.loginAs('standard')` &mdash; not
> `username.fill('standard_user')`. When saucedemo adds a seventh
> user, I update **one** const, not 17 specs.
>
> This matters for QA hand-off. A new tester reads `loginAs('locked')`
> and immediately knows the intent. They don't need to memorise
> magic strings."

(Optional flourish — Alt-tab to actual `LoginPage.ts` in editor for
3 seconds.)

> **TH cue:** "POM = test ที่อ่านเหมือน requirement &mdash; **ลด
> magic string** + onboard QA ใหม่ได้ใน 1 วัน"

---

## 6. Tag system end-to-end — 1 minute

➜ **Click slide 8 (17 tests / 17 sec stats)**

> "**One tag system flows through everything.**
>
> Same `@smoke / @e2e / @regression / @visual` markers gate:
> - **Playwright** &mdash; `npx playwright test --grep @smoke`
> - **Hub stage-5 dropdown** &mdash; QA picks tag at runtime
> - **Schedule definition** &mdash; daily smoke at 02:00, nightly e2e,
>   weekly regression
> - **Release gate's Run Scope criterion** &mdash; smoke alone is
>   insufficient; gate requires `@e2e` or `All`
>
> **17 tests** broken down: 4 smoke (12s, pre-merge), 2 e2e
> (nightly + release), 10 regression (weekly), 1 visual."

> **TH cue:** "tag เดียวคุมทั้ง CI / hub / schedule / release gate
> &mdash; **ไม่มี duplicate config**"

(Alt-tab to terminal — already cued up:)

```bash
cd projects/saucedemo
npm run test:smoke     # 4 tests / 12s
```

> "Watch the timing &mdash; about 12 seconds against the live site."

---

## 7. Open the hub — 2 minutes

➜ **Open browser tab 2: <http://localhost:8080>**

> "This is the hub at `localhost:8080`. **Two projects** registered
> &mdash; `saucedemo-e2e` is active, `saucedemo-mobile` is in
> **planning**. The release gate **knows** about that and skips
> planning projects in its verdict."

### Dashboard tab (20 s)
➜ Click slide 10 if browser-sharing is unstable.

> "Trend chart shows the last two weeks of runs. **Notice the dip
> on May 1st** &mdash; three failures out of 17. That's seeded data,
> but it's the friday-deploy bad-luck pattern you'd actually see in
> prod. The team can spot it in three seconds without opening any
> log file."

### Bug Tracker tab (40 s) &mdash; **lean in here**
> "Four sample bugs of varying severity. Aging badges show how long
> each has been open. The bug tracker is **wired into the release
> gate** &mdash; if a Critical or High bug is `Open`, the gate
> verdict is NOGO."
>
> "Severity ladder follows my prior team's convention:
> - **Critical** &mdash; system unusable. Hard fail.
> - **High** &mdash; feature broken, no workaround. Hard fail.
> - **Medium** &mdash; workaround exists. Warn band.
> - **Low** &mdash; cosmetic. Tracked, not blocking.
>
> Each bug has assignee + creation date + aging &mdash; **enough to
> run a triage standup off the dashboard alone**."

### Release Gate tab (1 min) &mdash; **the QA mindset showcase**
➜ **Click slide 13 (6 criteria) for clarity**.

> "Six criteria for a Playwright project:
>
> 1. **Run scope** &ge; `@e2e` &mdash; smoke alone is insufficient.
>    Catches the case where someone runs only @smoke and ships.
> 2. **Pass rate** &ge; 80%, configurable per project.
> 3. **No Critical bugs open** &mdash; hard fail.
> 4. **No High bugs open** &mdash; hard fail.
> 5. **Screenshots present** &mdash; evidence the tests actually ran.
> 6. **HTML report ready** &mdash; reviewers can debug without rerunning.
>
> This is a verdict based on **evidence**, not vibes. The gate file
> is 200 lines of Python &mdash; easy to audit, easy to extend per
> project. **The point is: runs are evidence, gate is policy.** Same
> suite drives multiple environments without changing test code."

### Pipeline tab (15 s)
➜ Click ▶ on the smoke run to demo live SSE.

> "One click runs `npx playwright test --grep @smoke`. Output streams
> via SSE &mdash; same logs as the terminal, but visible to the team."

### Schedule tab (15 s)
> "Daily smoke at 02:00 UAT. Failures get logged the same way manual
> runs do &mdash; **scheduler isn't a separate world**, results flow
> through the same release gate."

---

## 8. Architecture &middot; the JSON trade-off — 30 seconds (compressed)

➜ **Click slide 17 (Why JSON?)** *only if interviewer asks or time allows*.

> "Quick architectural note: state lives in **JSON files**, not a
> database. Auditable, recoverable, no migration drama. Trade-off
> is honest &mdash; doesn't scale to multi-team. For a small QA hub,
> sweet spot. Postgres swap is ~1 day work if needed."

(For pure-QA interviews this slide is optional. Skip if running short.)

---

## 9. CI + roadmap — 30 seconds

➜ **Click slide 18 (GitHub Actions YAML)**

> "Every push runs the tests on Ubuntu in CI. Playwright HTML report
> uploads as a 14-day artifact, so reviewers debug failures **without
> running anything locally**."

➜ **Click slide 19 (roadmap)**

> "Four next things: live deployment so anyone can click a URL,
> mobile-viewport project (already registered as `planning`), Allure
> for richer trends, Slack webhook for fail-only notifications."

---

## 10. Close — 30 seconds

➜ **Click slide 20 (thanks)**

> "Repo's public, MIT licensed. One command to run locally:
> `./setup.ps1`. Happy to dive into any part &mdash; the
> Playwright suite, the **release gate logic**, the **tag system
> end-to-end**, or the bug-tracker schema. **Which one would be
> most useful for the role you're hiring for?**"

> **TH version:** "Repo เปิด public MIT license ครับ ติดตั้งเครื่อง
> เดียว `./setup.ps1` แล้วเปิด `localhost:8080` &mdash; ถ้ามี part
> ไหนอยากให้เจาะ เช่น Playwright spec, release gate logic, tag
> system, bug tracker schema &mdash; ผมยินดีครับ"

---

## Q&A &mdash; QA-specific anticipated questions

### A. Test design & strategy

| Question | Answer |
|---|---|
| **Test pyramid placement?** | "These 17 tests are all UI/E2E by intent &mdash; this is a portfolio piece, so coverage demonstrates the *style*, not a real pyramid. In a production project I'd push validation/calculation logic into unit tests under each component, integration tests for API contracts, and keep E2E for critical user journeys only. **E2E is expensive &mdash; spend it on what only E2E can verify.**" |
| **Coverage rationale?** | "Two axes. **By tag**: smoke = critical, e2e = checkout flow, regression = edge cases. **By user**: 6 users * core flows = matrix. The gap I'd flag honestly &mdash; no API-level tests yet. Saucedemo doesn't expose a clean API, so I'd add MSW or contract tests in a real prod codebase." |
| **How do you decide what to automate?** | "Three filters. (1) **High-value path** &mdash; if it breaks, customer hurts. (2) **Stable spec** &mdash; if requirements churn weekly, the test churns too. (3) **Hard-to-test-manually** &mdash; visual regression, performance edge cases. Manual exploratory still beats automation for new features in week 1." |
| **Exploratory vs scripted testing?** | "Both. Automation catches regressions you've already found. Exploratory finds the new ones. I'd allocate ~70/30 in a mature suite, ~40/60 early in a project. The hub's bug tracker is built for exploratory finds &mdash; tester logs the bug there, fix shows up in release gate criterion 3-4." |
| **Visual regression flakiness?** | "Real risk. In TS_06 I went *stronger* than pixel-diff &mdash; assert that all six product `<img src>` collapse to a single URL. **That's the actual bug**, not a rendering artifact. Pixel-diff baselines also break across OS in CI. For genuine visual diffs in prod, I'd use Percy/Chromatic with masked dynamic regions." |

### B. Tooling & framework choices

| Question | Answer |
|---|---|
| **Why Playwright over Cypress / Selenium?** | "Three reasons. (1) **Native multi-tab + iframe** &mdash; Cypress sandboxes break third-party SSO. (2) **Auto-waiting locators** &mdash; less flake than Selenium's WebDriverWait. (3) **Trace viewer** &mdash; click through every action of a failed run with DOM snapshots. Cypress has better DX out of the box, but Playwright's API matures faster and parallel-by-default cut my CI time in half." |
| **Why TypeScript not Python (with pytest-playwright)?** | "Playwright TS API is roughly **a year ahead** of Python &mdash; locator chaining, auto-waiting, trace integration. For desktop tests I still pick pytest because Python's win32com / pywinauto ecosystem is unmatched. **Match the language to the SUT, not the team's preference.**" |
| **What did you cut for the 1-week timeline?** | "Live deployment, mobile project activation, Allure, Slack webhook. All listed in roadmap, all <2 day items. **The cut I'm proudest of: I didn't add Cucumber/BDD.** Page Object + descriptive test names already give readable specs. BDD adds a Gherkin layer that nobody non-technical actually reads in practice." |

### C. Process & team workflow

| Question | Answer |
|---|---|
| **How do you handle flaky tests?** | "Layered. (1) **Auto-retry** in CI (`retries: 1`). (2) **Trace + video + screenshot** saved on fail &mdash; debug from artifact, no rerun needed. (3) Gate counts a flake-then-pass as pass &mdash; doesn't block on retry-passing tests. (4) **Track flake rate per spec** &mdash; if a single spec flakes >5% over 30 days, quarantine it and fix root cause. Common culprits: race conditions on `networkidle`, animations not awaited, fixture pollution." |
| **Test data strategy?** | "Saucedemo's six users are read-only &mdash; convenient. For mutating flows (cart, checkout) the test cleans up via logout → fresh login per spec. **No fixtures needed at this size.** In production: API setup hooks or DB seeding via migration, never hard-coded IDs, always generate unique test data per run to avoid collisions." |
| **Shift-left strategy?** | "Tag-based blast-radius. **`@smoke` runs pre-merge in CI** (12s &mdash; fits in PR feedback loop). **`@e2e` runs nightly** &mdash; catches integration regressions before standup. **`@regression` runs weekly** &mdash; broader coverage, slower OK. Visual + perf get separate longer cadences. Goal: developer feedback in <1 min, team feedback in <12 hours." |
| **Bug triage workflow?** | "Tester logs in **Bug Tracker tab** with severity. Daily standup: open Critical/High first &mdash; release gate auto-blocks the build until Resolved. Medium/Low tracked but don't block. **The point: bug tracker isn't a separate Jira workflow &mdash; it's wired into the release verdict.** Reduces 'bug logged but forgotten' problem." |
| **Onboarding a new QA hire?** | "Day 1: clone, `./setup.ps1`, run `npm test`. Day 2: read TOUR.md (15 min), open `LoginPage.ts` &mdash; understand POM. Day 3: write a new spec for a missing user flow following existing template. Day 5: triage the bug tracker, log a real bug, watch it flow into the gate. **Self-documentation is in the User Guide tab inside the hub itself** &mdash; no separate Confluence." |
| **CI/CD integration?** | "GitHub Actions runs tests on every push + PR. **Playwright HTML report uploaded as artifact, 14-day retention.** Reviewer clicks artifact link in PR, opens HTML report, debugs failure without cloning. **No Slack noise** for routine passes &mdash; only failures + scheduled-run failures (planned, not yet shipped)." |

### D. Failure handling & quality

| Question | Answer |
|---|---|
| **How would you measure QA team success?** | "Three metrics, ranked. (1) **Escape rate** &mdash; bugs found in prod / total bugs found. Target <5%. (2) **Mean time to detect** &mdash; how fast a regression is caught after merge. Target <1 day for critical paths. (3) **Suite stability** &mdash; flake rate, pass-rate trend. **Coverage % is *not* on this list** &mdash; it's a vanity metric without context." |
| **What's the biggest risk in this suite?** | "Honest answer: **all 17 tests hit live saucedemo.com**. If that site goes down or changes copy, my CI breaks &mdash; even though my code is fine. Mitigation in prod: record/replay HAR, or run against a staged environment with controlled seed data. For portfolio purposes I accepted the risk." |
| **What if a test is wrong, not the code?** | "Common failure mode. Process: (1) **assume the test is right first** &mdash; don't tweak assertions until you've ruled out a real regression. (2) Cross-reference with manual repro on the dev's machine. (3) If test is genuinely outdated (new requirement), update with PR + comment linking the spec change. **Never silently 'fix' an assertion to make CI green.**" |
| **Cross-browser strategy?** | "Currently chromium-only by config &mdash; portfolio scope. Production: Playwright supports Firefox + WebKit out of the box, just add to `projects:` array. **Browser-specific bugs are rare in modern code** &mdash; I'd run multi-browser nightly, not on every PR, to keep feedback fast." |
| **Mobile testing approach?** | "`saucedemo-mobile` is registered as `phase=planning`. Activation = uncomment the Pixel 7 viewport project in `playwright.config.ts`. **Same suite, mobile viewport, visual snapshots.** For real mobile (touch events, native gestures, real devices) I'd add Appium or BrowserStack &mdash; out of scope for this portfolio." |
| **Performance / load testing?** | "Out of scope here &mdash; Playwright is for functional E2E. For performance I'd use **k6** for load (developer-friendly JS scripting) or **Lighthouse CI** for frontend perf budgets. Could wire Lighthouse into a stage-7 in this hub if needed &mdash; ~half-day work." |
| **Accessibility testing?** | "Honest gap &mdash; no a11y tests in this suite. In production I'd add **axe-playwright** as a stage-6 check and gate on no Critical/Serious violations. Saucedemo wouldn't pass &mdash; that's actually a feature, lets me demonstrate the gate catching a real failure." |

---

## Failure recovery — if something breaks live

- **Hub won't start** → `python -m hub.app` from the repo root.
  Check port 8080 isn't busy: `netstat -ano | findstr :8080`.
- **Tests fail on saucedemo.com** → site is occasionally slow.
  `npm run test:smoke` (4 tests, 12 s) is a faster fallback.
- **Slides won't load images** → confirm you're opening `SLIDES.html`
  via `file://` from the same folder as `screenshots/`. Don't double-
  click from outside the folder.
- **Network blocked** → use the prerecorded screenshots in
  `docs/screenshots/` and walk through the slide deck only.

---

## Timing budget (QA-tuned)

| Section | Target | Cumulative |
|---|---|---|
| 1. Opening | 0:30 | 0:30 |
| 2. The QA problem | 1:00 | 1:30 |
| 3. Tech stack (compressed) | 0:30 | 2:00 |
| 4. Test design — 6 users | 1:30 | 3:30 |
| 5. Code — POM | 1:00 | 4:30 |
| 6. Tag system + live run | 1:00 | 5:30 |
| 7. Hub walkthrough (Bug + Gate focus) | 2:30 | 8:00 |
| 8. JSON note (skippable) | 0:30 | 8:30 |
| 9. CI + roadmap | 0:30 | 9:00 |
| 10. Close | 0:30 | 9:30 |
| **Q&A** | 5:30 | 15:00 |

If running short — drop section 8 (JSON), compress section 3 even
further. **Do not cut sections 4-7** &mdash; those are the QA showcase.

---

## What to emphasise / what to skip

| Lean in | Skip / mention only if asked |
|---|---|
| Test design rationale (6 users = 6 scenarios) | Vue migration / strangler-fig |
| Page Object Model + onboarding angle | Architecture diagram details |
| Tag system end-to-end | JSON vs SQL trade-off (unless asked) |
| Release gate as **evidence-based verdict** | ~70 Flask routes |
| Bug tracker → release gate linkage | SSE / streaming logs (mention once) |
| Visual test = assert behaviour, not pixels | Strangler-fig naming |
| What you'd cut / honestly didn't ship | Roadmap items beyond "what's next" |

If interviewer asks about the **frontend** (Vue v2 dashboard,
strangler-fig migration, Pinia stores) &mdash; brief answer: "I built
that to make the hub usable for the team, but it's not the core
QA story. Happy to dig in if useful." Don't volunteer it.
