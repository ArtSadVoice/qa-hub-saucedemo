# Demo script — QA Hub for saucedemo.com

Live walkthrough script (~12-15 minutes). Use when presenting to HR /
hiring manager. Slides at `docs/SLIDES.html`. Repo:
<https://github.com/ArtSadVoice/qa-hub-saucedemo>.

> **Tone tip:** speak in plain language. The slides cover *what* —
> your job in the live demo is the *why*. Aim for one sentence per
> point, then click.

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
> project I built — a QA orchestration hub paired with a Playwright
> TypeScript suite that tests saucedemo.com end-to-end. I built it
> in one week to demonstrate how I'd structure test automation for
> a small QA team."

> **TH:** "สวัสดีครับ ผมจะ walk through portfolio ของผม — เป็น hub
> สำหรับจัดการ test automation ที่ใช้ทดสอบ saucedemo.com แบบ end-to-end
> ทั้งหมดสร้างใน 1 สัปดาห์ เพื่อโชว์ว่า ถ้าผมต้องวาง test automation
> ให้ทีม QA เล็กๆ ผมจะวางยังไง"

➜ **Click slide 1**

---

## 2. The pitch — 1 minute

> "Most QA teams I've seen run Playwright or pytest locally. Each
> engineer sees their own results. Bugs live in heads. When the team
> lead asks 'are we ready to ship?' the answer is a feeling, not data.
>
> This hub solves that. **One dashboard, tag-based runs, JSON state,
> automated release verdict.**"

➜ **Click slide 2 (Problem / Solution side-by-side)**

Pause for 5 seconds. Let them read.

---

## 3. Tech stack — 45 seconds

➜ **Click slide 3**

> "Six pieces. Tests are **Playwright TypeScript** — Page Object Model
> with tag-based filtering. Hub backend is **Flask** with about 70
> routes and Server-Sent Events for live logs. Frontend is **Vue 3**
> in a strangler-fig migration alongside a legacy vanilla-JS dashboard.
> State lives in **JSON files** — I'll explain that choice in a moment.
> CI is **GitHub Actions**, and the test target is **saucedemo.com**."

> **TH cue:** strangler-fig = "เปลี่ยน UI ทีละชิ้น โดยไม่ต้องหยุด
> ใช้งานของเก่า"

---

## 4. Architecture — 1 minute

➜ **Click slide 4 (architecture diagram)**

> "This is the data flow. Browser hits Flask. Flask owns three things:
> the JSON state files, a release-gate evaluator, and a scheduler
> thread. When you click 'Run Tests', Flask spawns
> `npx playwright test` from the project's folder and streams stdout
> back to the browser via SSE.
>
> The point is: **the hub doesn't run tests. It orchestrates.** The
> tests stay portable — you can run them from CLI, CI, or the hub
> without changing a line."

---

## 5. Show the target — 30 seconds

➜ **Click slide 5 (saucedemo home)**

> "The system under test. Saucedemo is a public e-commerce demo with
> six built-in test users. I picked it because each user is a natural
> test scenario — happy path, locked account, broken images, slow
> performance, validation bugs."

➜ **Click slide 6 (six users grid)**

> "These six users **are** my test plan."

---

## 6. Show the code — 1 minute

➜ **Click slide 7 (Page Object Model snippet)**

> "Here's why Page Object Model matters. The `TEST_USERS` const
> documents saucedemo's six users in one place. The spec body reads
> like a requirement: `loginAs('standard')` not
> `username.fill('standard_user')`. When saucedemo adds a seventh
> user, I update **one** const, not 17 specs."

> **TH cue:** "spec อ่านเหมือน requirement ไม่ใช่อ่านเหมือน code"

(Optional flourish — Alt-tab to actual `LoginPage.ts` in editor for
3 seconds.)

---

## 7. Show the tests run — 1.5 minutes

➜ **Click slide 8 (17 tests in 17 seconds)**

> "Seventeen tests across login, inventory, cart, checkout, logout,
> and one visual baseline. Tag-filtered: smoke, e2e, regression,
> visual."

(Alt-tab to terminal — already cued up:)

```bash
cd projects/saucedemo
npm test
```

> "Watch the timing — about 17 seconds against the live site."

(Wait for green output. If it takes longer, use the time to talk
through the next slide.)

---

## 8. Open the hub — 2 minutes

➜ **Open browser tab 2: <http://localhost:8080>**

(Or click slide 9-10 if running in slides-only mode.)

> "This is the hub at `localhost:8080`. Two projects registered —
> `saucedemo-e2e` is active, `saucedemo-mobile` is in planning.
> The release gate **knows** about that and skips planning projects."

**Walk through the tabs in this order:**

### Dashboard tab (30 s)
> "Trend chart shows the last two weeks of runs. Notice the dip on
> May 1st — three failures out of 17. That's seeded data, but in
> production it's the friday-deploy-bad-luck pattern you'd actually
> see. The team can spot it in three seconds without opening any logs."

### Pipeline tab (20 s)
➜ Click ▶ on the smoke run.
> "One click runs `npx playwright test --grep @smoke`. Output streams
> via SSE — same logs you saw in the terminal, but now visible to the
> whole team."

### Bug Tracker tab (20 s)
> "Four sample bugs, varying severity. Aging badges show how long each
> has been open. The release gate reads from this file."

### Release Gate tab (40 s)
➜ **Click slide 13 (6 criteria card)** if you want to enumerate.
> "Six criteria for a Playwright project: run scope, pass rate, no
> critical bugs, no high bugs, screenshots, HTML report. This is a
> verdict based on **evidence**, not vibes. The gate file is 200 lines
> of Python — easy to audit, easy to extend."

### Schedule tab (15 s)
> "One daily smoke run at 02:00 UAT. Scheduler is a background thread.
> Failures get logged to `run_history.json` the same way manual runs do."

---

## 9. Why JSON state — 45 seconds

➜ **Click slide 17 (Why JSON?)**

> "I made one architecturally non-obvious choice: **JSON files instead
> of a database.** Four reasons. Auditable — every state change shows
> up in `git diff`. Recoverable — copy/paste one file to restore.
> No migration drama — schema lives in code. Fast enough — atomic
> temp+rename, sub-millisecond parse.
>
> Trade-off: this doesn't scale to multi-team multi-writer. But for
> a small QA hub, it's the sweet spot. I want to be honest about
> that trade-off — I'd switch to Postgres if the team grew past
> ~10 engineers."

> **Why this slide matters for HR:** shows you can articulate
> trade-offs, not just choices.

---

## 10. CI + roadmap — 45 seconds

➜ **Click slide 18 (GitHub Actions YAML)**

> "Every push runs the tests on Ubuntu in CI. The Playwright HTML
> report uploads as an artifact, so reviewers can debug failures
> without running anything locally."

➜ **Click slide 19 (roadmap)**

> "Four things I'd add next. Live deployment so anyone can click a
> URL. Mobile-viewport project — the slot is already registered as
> `planning`. Allure for richer trends. Slack webhook for fail-only
> notifications."

---

## 11. Close — 30 seconds

➜ **Click slide 20 (thanks)**

> "Repo's public, MIT licensed. One command to run locally —
> `./setup.ps1`. Happy to dive into any part you want — the
> Playwright suite, the release gate logic, the strangler-fig
> migration. What stood out to you?"

> **TH version:** "Repo เปิด public พร้อม MIT license ครับ ติดตั้ง
> ที่เครื่องคำสั่งเดียว `./setup.ps1` แล้วเปิด `localhost:8080`
> ถ้ามี part ไหนอยากให้เจาะลึก เช่น โค้ดเทส กฎ release gate
> หรือการย้าย UI &mdash; ผมยินดีครับ ส่วนไหนน่าสนใจที่สุดสำหรับคุณครับ?"

---

## Q&A prep — anticipated questions

| Question | One-line answer |
|---|---|
| **Why Playwright over Cypress / Selenium?** | Native multi-tab, real network interception, parallel by default. Cypress is great DX but the iframe sandbox blocks third-party login flows. |
| **Why TypeScript not Python?** | The Playwright TS API is a year ahead — locator chaining, auto-waiting, trace viewer integration. Python suite stays in Pytest for desktop tests. |
| **Why two dashboards?** | Strangler-fig migration. Vue 3 ships incrementally; legacy stays as fallback. Both consume the same `/api/*`. Zero-downtime modernisation. |
| **What if you scale beyond JSON?** | Swap `state.py` (the read/write layer) for SQLAlchemy. Endpoints stay the same. ~1 day of work. |
| **How do you handle flaky tests?** | Playwright auto-retry on CI (configured in `playwright.config.ts`). Failed tests get a trace + video saved to `test-results/`. Gate counts a flake-then-pass as pass. |
| **What's the test data strategy?** | Saucedemo's six users are read-only. For mutating tests (cart, checkout) the test cleans up via logout → fresh login per spec. No fixtures needed. |
| **Why not Cucumber / BDD?** | Page Object + descriptive test names already gives readable specs. BDD adds a Gherkin layer that nobody non-technical actually reads in practice. |
| **Visual regression — won't that break constantly?** | Only `problem_user` runs visual right now (1 test). Baseline regenerated when intentionally changed. Mask dynamic regions. Trade-off accepted. |
| **What did you cut for the 1-week timeline?** | Live deployment, Slack webhook, Allure, mobile project. All listed in roadmap, all <2 day items. |
| **Solo project — how would you work in a team?** | This started as a fork of an internal hub I built for a real team. Same pattern: PR with tests + screenshots, hub config diff in PR description, gate verdict in CI annotation. |

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

## Timing budget

| Section | Target | Buffer |
|---|---|---|
| 1. Opening | 0:30 | 0:30 |
| 2. Pitch | 1:00 | 1:30 |
| 3. Tech stack | 0:45 | 2:15 |
| 4. Architecture | 1:00 | 3:15 |
| 5-6. Target + users + code | 2:00 | 5:15 |
| 7. Live test run | 1:30 | 6:45 |
| 8. Hub walkthrough | 2:00 | 8:45 |
| 9. Why JSON | 0:45 | 9:30 |
| 10. CI + roadmap | 0:45 | 10:15 |
| 11. Close | 0:30 | 10:45 |
| **Q&A** | 4:00 | 14:45 |

If running short — drop section 9 (Why JSON) and tuck it into Q&A.
