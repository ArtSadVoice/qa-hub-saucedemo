Run a specific failing test with full trace enabled, then analyze the failure and suggest a fix.

The argument $ARGUMENTS is the TSID or test name, e.g. `TS_01` or `TS_04_sub_questions`.

Steps:

1. Resolve the argument to the matching spec file under tests/e2e/ (same logic as /test-file)

2. Run the test with trace:
```bash
npx playwright test <resolved-file> --reporter=list --trace=on
```

3. Read the test output carefully. For each failing test:
   - Show the test name and error message
   - Show the selector or assertion that failed
   - Read the corresponding spec file and SurveyPage.ts to understand what was expected

4. Diagnose the root cause:
   - Wrong selector? (element not found, strict mode violation)
   - Wrong expected text?
   - Timing/navigation issue?
   - Survey UI changed?

5. Suggest a concrete fix with the exact code change needed in the spec file or SurveyPage.ts

6. Ask the user if they want you to apply the fix.

Note: Do NOT speculatively change the code before diagnosing. Read the actual error first.
