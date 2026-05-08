Show a quick project status summary without running any scripts.

Read the following files and report:

1. **Input Excel** — read `input/*.xlsx` (TCM sheet):
   - Count TCs per TSID with status breakdown (Pass/Fail/In-Progress/Block/Cancel/Not Start)
   - Show overall totals and Accuracy %

2. **Screenshots** — list `screenshots/*.png`:
   - Count total PNGs available
   - List any TCID screenshots that exist vs what is expected from TCM
   - Note if chart_summary.png exists

3. **Output** — check `output/` for latest non-backup .docx:
   - Show filename, size, last modified time

4. **Watch status** — check if `.snapshot.json` exists in logs/:
   - If yes, show when it was last updated

Present results as a compact summary table. Flag any gaps (e.g. TCIDs missing screenshots, no output file yet).
