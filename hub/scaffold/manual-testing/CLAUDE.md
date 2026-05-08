# {{PROJECT_NAME}}

## Project info
- **App name**: {{PROJECT_NAME}}
- **Base URL**: `{{BASE_URL}}`
- **Type**: manual-testing (TCM → Manual Test → Word Report)
- **figma_url**: `{{FIGMA_URL}}`

## Pipeline stages (manual-testing)
1. วาง Excel TCM ใน `input/`
2. BA Agent วิเคราะห์ requirements → ba_output JSON + สร้าง TCM Excel
3. Add Charts to Excel
4. *(ข้าม)* Generate Playwright Spec
5. *(ข้าม)* Run Playwright Tests
6. *(ข้าม)* Screenshot Injection
7. QA อัปเดต Pass/Fail ใน TCM Excel ด้วยมือ แนบ screenshot ใน `screenshots/`
8. รัน `python scripts/generate_report.py` — สร้าง Word report
9. Download report

## Key folders
- `input/`         — Excel TCM files
- `output/`        — Word report output
- `screenshots/`   — Manual screenshots (ถ่ายเองแล้ววางที่นี่ ชื่อไฟล์ตาม TCID)
- `templates/`     — Excel & Word templates
- `scripts/`       — Python pipeline scripts
- `logs/`          — BA output JSON, run logs
- `docs/reviews/`  — Cross-review และ TCM review reports
- `requirements/`  — Requirement documents
- `figma/`         — Figma export PNG

## Agents (.claude/agents/)
| Agent | เรียกใช้เมื่อ |
|-------|-------------|
| `ba-agent` | มี requirements ใหม่ หรือต้องการแปลง Figma/doc → TCM |
| `qa-agent` | ต้องการ TCM_GENERATE, COVERAGE_CHECK, RISK_ANALYSIS, TEST_DATA, BUG_REPORT, TRACEABILITY |
| `excel-review-agent` | ตรวจคุณภาพ TCM Excel ก่อน generate report |
| `cross-review` | ตรวจ gaps ทุก layer ก่อน release หรือเมื่อ pass rate < 80% |
