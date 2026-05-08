Inject screenshots from screenshots/ into the latest Word output file.

Run:
```bash
python -X utf8 scripts/screenshot_injector.py
```

After running, report:
- How many screenshots were injected (total count)
- List each TCID and filename injected
- Note if chart_summary.png was included
- If any screenshots are missing (TCIDs in output with no matching PNG), list them
- Show the output filename and size

If the injector fails, show the error and suggest whether it's a file-lock issue (Word open) or a missing input file.
