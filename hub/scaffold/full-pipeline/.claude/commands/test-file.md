Run a specific Playwright spec file. The argument is the TSID or filename, e.g. `/test-file TS_01` or `/test-file TS_04_sub_questions`.

Resolve the argument $ARGUMENTS to the matching file under tests/e2e/ (add .spec.ts if needed), then run:

```bash
npx playwright test tests/e2e/$ARGUMENTS.spec.ts --reporter=list
```

If $ARGUMENTS is empty, ask the user which test file to run and list the available spec files.

Show the results with pass/fail status for each test case, plus error details for any failures.
