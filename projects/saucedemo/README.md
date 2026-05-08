# Saucedemo — Playwright TS Suite

End-to-end test suite for [https://www.saucedemo.com](https://www.saucedemo.com),
written in TypeScript with `@playwright/test`. Registered with the QA Hub
Demo as a `playwright-only` project (run via the hub's Stage 5 button or
directly with `npm test`).

## What's covered

| Test file | TCs | Tags |
|-----------|-----|------|
| `TS_01_login.spec.ts` | 4 | smoke, regression × 3 |
| `TS_02_inventory.spec.ts` | 4 | smoke, regression × 3 |
| `TS_03_cart.spec.ts` | 4 | smoke, e2e, regression × 2 |
| `TS_04_checkout.spec.ts` | 3 | e2e, regression × 2 |
| `TS_05_logout.spec.ts` | 1 | smoke |
| `TS_06_problem_user.visual.spec.ts` | 1 | visual |
| **Total** | **17** | |

Default suite (no `--grep`) runs everything. Tag-based subsets:

```bash
npm run test:smoke       # 4 tests, < 30s — happy path sanity
npm run test:e2e         # 2 tests, ~1 min — full checkout flows
npm run test:regression  # 10 tests — edge cases, sort, validation
npm run test:visual      # 1 test — problem_user visual snapshot
```

## Setup

```bash
cd projects/saucedemo
npm install
npx playwright install chromium
npm test
```

Or to debug:

```bash
npm run test:headed       # opens browser
npx playwright test --ui  # Playwright UI mode
```

## Page Objects

```
tests/pages/
├── LoginPage.ts        — TEST_USERS list + loginAs helper
├── InventoryPage.ts    — sort, add/remove cart, logout
├── CartPage.ts         — list items, remove, checkout
└── CheckoutPage.ts     — 3-step checkout state machine
```

The `TEST_USERS` const in `LoginPage.ts` documents saucedemo's six built-in
test users (`standard_user`, `locked_out_user`, `problem_user`, etc.) so
new specs can reference them by intent.

## Running via QA Hub Demo

After installing the hub (`../hub/`), the saucedemo project is registered
in `config.json.example` with two entries:

| Project ID | Phase | Purpose |
|------------|-------|---------|
| `saucedemo-e2e` | active | Default suite via Stage 5 ▶ |
| `saucedemo-mobile` | planning | Visual snapshots on Pixel 7 viewport (commented out in `playwright.config.ts`) |

The hub auto-runs `npx playwright test --reporter=list --grep @<tag>` from
this project's folder; junit XML is parsed and appended to
`run_history.json` automatically.
