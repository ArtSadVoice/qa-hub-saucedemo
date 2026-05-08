# {{PROJECT_NAME}}

## Project info
- **App name**: {{PROJECT_NAME}}
- **Base URL**: `{{BASE_URL}}`
- **Type**: full-pipeline (TCM → Playwright → Report)
- **figma_url**: `{{FIGMA_URL}}`

## Pipeline stages
1. วาง Excel TCM ใน `input/`
2. รัน `python scripts/generate_tcm.py` — สร้าง test cases จาก Excel
3. รัน Playwright tests: `npx playwright test`
4. รัน `python scripts/generate_report.py` — สร้าง Word report

## Key folders
- `input/`         — Excel TCM files
- `output/`        — Word report output
- `screenshots/`   — Test screenshots
- `templates/`     — Excel & Word templates
- `scripts/`       — Python pipeline scripts
- `tests/e2e/`     — Playwright test specs
- `logs/`          — BA output JSON, run logs
- `docs/reviews/`  — Cross-review และ TCM review reports

## Agents (.claude/agents/)
| Agent | เรียกใช้เมื่อ |
|-------|-------------|
| `ba-agent` | มี requirements ใหม่ หรือต้องการแปลง Figma/doc → TCM |
| `qa-agent` | ต้องการ TCM_GENERATE, COVERAGE_CHECK, RISK_ANALYSIS, TEST_DATA, BUG_REPORT, TRACEABILITY |
| `playwright-agent` | เขียน/รัน/แก้ Playwright spec |
| `excel-review-agent` | ตรวจคุณภาพ TCM Excel ก่อน generate report (บล็อก release ถ้ามี Critical) |
| `cross-review` | ตรวจ gaps ทุก layer ก่อน release หรือเมื่อ pass rate < 80% |
| `release-approval` | ตรวจ release gate ทุกข้อ สร้าง approval checklist + sign-off record |

## Slash Commands (.claude/commands/)
| Command | ทำอะไร |
|---------|--------|
| `/pipeline` | รัน full pipeline: BA → TCM → Playwright → Report |
| `/ba-agent [file]` | วิเคราะห์ requirements → สร้าง TCM Excel |
| `/test` | รัน Playwright tests ทั้งหมด (UAT) พร้อม ENV pre-check |
| `/test-tag @tag [--env]` | รัน tests ตาม tag และ environment พร้อม ENV pre-check |
| `/test-headed` | รัน tests แบบเปิด browser |
| `/test-file [file]` | รัน test ไฟล์เดียว |
| `/traceability` | สร้าง Requirement ↔ TC ↔ Result matrix |
| `/bug-assign [id] [--to name]` | มอบหมาย bug + ส่ง Slack notification |
| `/report` | Generate Word report |
| `/report-send [--channel email\|slack\|both]` | ส่ง report ผ่าน Email / Slack |
| `/inject` | Screenshot injection เข้า Word report |
| `/approve-release` | ตรวจ release gate ทุกข้อ + สร้าง approval record |
| `/schedule-run [--tag] [--env]` | Trigger run ผ่าน Hub API |
| `/status` | แสดง pipeline stage status |
| `/dashboard` | เปิด Hub dashboard |
| `/start` | เริ่ม project ใหม่ |
| `/write-req [feature]` | สร้าง requirement file |
| `/summarize-input` | สรุป input requirements |
| `/watch` | Watch mode — รัน test อัตโนมัติเมื่อไฟล์เปลี่ยน |
| `/debug-test` | Debug test ที่ fail |

## Release Workflow (แนะนำ)

```
/test-tag @e2e              # ตรวจ pass rate
/excel-review-agent         # ตรวจ TCM quality (บล็อกถ้า Critical)
/cross-review               # ตรวจ gaps ทุก layer
/traceability --save        # บันทึก requirement ↔ TC matrix
/approve-release            # ตรวจ gate ทุกข้อ + สร้าง sign-off checklist
/report                     # Generate Word report
/report-send                # ส่ง report ให้ทีม
```

## Pre-flight Guards (ใส่ไว้กัน gap ที่เคยเจอจริง)

Pipeline จะ **abort พร้อม error ที่อ่านง่าย** ถ้าเจอเงื่อนไขเหล่านี้ — แทนที่จะ silently corrupt:

### Guard 1: Excel-overwrite race
- Trigger: มี `~$*.xlsx` lock ใน `input/` (Excel desktop เปิดไฟล์ค้าง)
- ใส่ใน: `scripts/generate_tcm.py`, `scripts/orchestrator.py` (ก่อน Stage 2)
- Why: Excel เก็บ in-memory snapshot — ถ้า script เขียน xlsx ระหว่าง Excel เปิดอยู่ Excel จะ save ทับด้วย snapshot เก่าทีหลัง ทำให้ TS หาย/ตกหล่นโดยไม่มี error
- Fix: ปิด Excel แล้วรันใหม่

### Guard 2: Template structural validation
- Trigger: `templates/Test_Result_Template.docx` มี duplicate `w:styleId`, ขาด core styles, ขาด anchor headings, หรือ table น้อยเกินไป
- ใส่ใน: `scripts/generate_report.py` (ก่อน load template)
- Why: Template ที่ download มาจากภายนอก (เช่น v2_1) อาจ parse ได้แต่ Word เปิดไม่ได้ — ตรวจก่อน generate ดีกว่าเสียเวลาเปิดผลออกมาแล้ว fail
- Fix: รัน `python scripts/check_template.py` เพื่อดู issue, หรือ restore จาก `.bak_*` backup

### Guard 3: Office-lock retry (UX-friendly)
- ที่ enforce: `_preflight.wait_for_xlsx_unlocked` / `wait_for_docx_unlocked` ใช้ใน
  `generate_tcm.py`, `orchestrator.py`, `add_excel_charts.py`, `screenshot_injector.py`
- ทำงาน: ถ้าเจอ lock → รอ default 60s, print progress ทุก 10s; เมื่อ user ปิด Office → continue ต่อ; ถ้า timeout → abort พร้อม diagnostic
- เลือกใช้: writer scripts ทุกตัวที่อาจชน Office desktop

### Guard 4: Pre-commit hook
- ไฟล์: `.githooks/pre-commit` — ถ้า `templates/Test_Result_Template.docx` ติด staging จะรัน `check_template.py` อัตโนมัติ; reject commit ถ้า fail
- เปิดใช้: `git config core.hooksPath .githooks` (setup.bat / setup.ps1 ทำให้แล้ว)
- override: `git commit --no-verify` (ใช้เฉพาะกรณีรู้ว่าทำอะไร)

### ตรวจ template ก่อน swap (manual)
```bash
python scripts/check_template.py path/to/new_template.docx          # structural
python scripts/check_template.py path/to/new_template.docx --smoke  # + smoke test
```
Smoke test ลองเปิด docx ผ่าน:
1. python-docx round-trip (เร็ว, ตรวจ XML well-formed)
2. LibreOffice headless convert-to PDF (proxy ของ Word — ต้องมี soffice ใน PATH)
3. Word COM (ต้อง Windows + Office + `pip install pywin32`)
ถ้าไม่มี tool ภายนอกเลย → smoke test skip พร้อมแนะนำให้ install

## Project Provisioning (long-term workflow)

Two safe paths to spawn a new QA-pipeline project — both inherit Guards 1–4
automatically:

### Path A: Copy from canonical scaffold `C:/Automation/_hub/scaffold/`
**Single source of truth.** Updated by `scripts/refresh_scaffold.py` from
this (or any) live project after improvements land.

```bash
# (one-time per improvement) refresh canonical scaffold from current project
python scripts/refresh_scaffold.py --apply

# Spawn a new project — option 1: run init_project from current project
python scripts/init_project.py --name NewProj --url https://app.example.com
#   → init_project auto-detects _hub/scaffold/ and uses it as source
#   → CLAUDE.md placeholders {{APP_NAME}} / {{BASE_URL}} get filled
#   → forensic *.bak_* files are skipped during copy

# Spawn a new project — option 2: manual copy
cp -r C:/Automation/_hub/scaffold C:/Automation/NewProj
cd C:/Automation/NewProj
setup.bat                      # activates git hooks if .git exists
# Edit CLAUDE.md to fill {{APP_NAME}} / {{BASE_URL}} / {{FIGMA_URL}}
```

What's in scaffold:
- All scripts incl. `_preflight.py`, `check_template.py`, `sync_to_project.py`,
  `refresh_scaffold.py`
- `.githooks/pre-commit` template-validator hook
- Production `templates/Test_Result_Template.docx` (validated)
- Agents, slash commands, examples, docs
- CLAUDE.md with `{{APP_NAME}}` / `{{BASE_URL}}` / `{{FIGMA_URL}}` placeholders

What's NOT in scaffold (project-specific runtime + customer data):
- `*.bak_*` forensic backups
- Files under `input/`, `output/`, `screenshots/`, `logs/`, `archive/`
- Customer artifacts in `requirements/` (gitignored anyway)

### Path B: `git clone` from canonical repo
For teams: push this project to a private git remote, others clone:

```bash
git clone <remote-url> NewProj
cd NewProj
setup.bat                # activates core.hooksPath = .githooks
# Adjust CLAUDE.md, place new requirement docs in requirements/, etc.
```

Setup scripts (`setup.bat` / `setup.ps1`) both run
`git config core.hooksPath .githooks` — so the pre-commit guard is live
after `setup` completes, no manual step needed.

### Keeping existing projects in sync
For projects that were created BEFORE these guards landed, retrofit them:

```bash
python scripts/sync_to_project.py /path/to/older-project          # dry run
python scripts/sync_to_project.py /path/to/older-project --apply  # apply
# ...add --include-pipeline-scripts and/or --include-template if you want
# the writer-side preflight wires and the validated production template too
```

`sync_to_project.py` is idempotent (SAME files no-op), backs up DIFF files
before overwriting, and activates the hook if the target is a git repo.

## Template Requirements

`templates/Test_Result_Template.docx` ต้องมีองค์ประกอบเหล่านี้ครบ ไม่งั้น Guard 2 จะ block:

**Styles ที่ต้องมี** (ใน `word/styles.xml`, ไม่มี duplicate styleId):
`Normal`, `DefaultParagraphFont`, `TableNormal`, `TableGrid`,
`Heading1`, `Heading2`, `Heading3`, `Header`, `HeaderChar`, `Footer`, `FooterChar`

**Body anchors** (heading text): `5. Test Result`, `6. Type of Testing`, `TS_01:`

**Placeholders**: `{{PROJECT_CODE}}`, `{{PROJECT_NAME}}`, `{{PREPARED_DATE}}`, `{{APPLICATION_OVERVIEW_DESCRIPTION}}` (รวมอื่น ๆ ใน `scripts/generate_report.py`)

**Tables**: อย่างน้อย 4 — `tables[0]`=banner, `tables[1]`=project info, `tables[2]`=signoff anchor, `tables[3]`=summary anchor

**Design rules ที่ enforce ผ่าน script** (ไม่ต้องตั้งใน template เอง):
- Body font 12pt / Heading 14pt
- ทุก table มี all borders
- Signoff: customer (non-QA Hub Demo) ซ้าย / QA Hub Demo ขวา + company header row + 2 blank lines/cell สำหรับลายเซ็น
