Show the full workflow guide for starting a new project or continuing an existing one, from Requirements/Figma all the way to the final Word report.

Read `GETTING_STARTED.md` and present the workflow interactively:

1. First, ask the user which situation applies to them:
   - **A)** เริ่ม project ใหม่ทั้งหมด (new project from scratch)
   - **B)** มี project อยู่แล้ว ต้องการรัน test + generate report
   - **C)** มีปัญหา / ต้องการ troubleshoot

2. Based on their answer, guide them through the relevant phases only:

   **If A (new project):**
   - Phase 0: Check dependencies are installed
   - Phase 1: Copy project + configure URL
   - Phase 2: Choose path (AI Agent or manual Excel)
   - Then continue from Phase 3 onward

   **If B (existing project):**
   - Ask what stage they're at (have TCM Excel? have test results? need report?)
   - Jump directly to the right phase

   **If C (troubleshooting):**
   - Show the Troubleshooting table from GETTING_STARTED.md
   - Ask what specific error or issue they're seeing

3. For whichever phase they're starting at, show the exact commands to run and explain what each one does.

4. After each phase, confirm with the user before moving to the next phase.

Always reference the available skills where appropriate:
- `/test` → run all tests
- `/test-file <TSID>` → run one spec file
- `/debug-test <TSID>` → diagnose failing test
- `/report` → generate Word + chart
- `/inject` → inject screenshots into Word
- `/status` → check current project state
- `/dashboard` → open web UI
- `/watch` → auto-regenerate on Excel save
