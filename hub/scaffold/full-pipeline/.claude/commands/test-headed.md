Run all Playwright tests in headed mode so the browser is visible. Use slow-mo to make interactions easier to follow.

```bash
npx playwright test --headed --slow-mo=600 --reporter=list
```

Useful for debugging failing tests or verifying UI interactions visually. After the run, summarize pass/fail results.
