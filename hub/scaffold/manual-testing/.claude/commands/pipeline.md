Run the full agentic QA pipeline: BA Agent → TC Agent → Playwright Agent → Word Report.

If $ARGUMENTS is provided, use it as extra flags (e.g. `--skip-ba logs/ba_output_xxx.json` to resume from Stage 2).

Default run (full pipeline):
```bash
python -X utf8 scripts/orchestrator.py --figma-image "figma/survey_flow.png" --input "requirements/survey_logic.md"
```

Resume from Stage 2 (skip BA, reuse existing BA output):
```bash
python -X utf8 scripts/orchestrator.py --skip-ba <path-to-ba-output-json>
```

After completion, show:
1. Which stages ran successfully
2. Output files generated (Excel TCM, Playwright specs, Word report)
3. Playwright test summary (pass/fail counts)
4. Any errors encountered and how to fix them

If no figma image or requirements file exists, ask the user which input files to use.
