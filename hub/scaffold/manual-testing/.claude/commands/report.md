Generate the Word test result report from the latest TCM Excel file in input/.

Run:
```bash
python -X utf8 scripts/run.py
```

After completion:
1. Show the output file path (e.g. output/F_001_TestResult_YYYYMMDD.docx)
2. Show a summary: how many TCs were included, pass/fail counts if available
3. If the command fails, show the error and suggest a fix (common issue: wrong template path or missing Excel file in input/)
