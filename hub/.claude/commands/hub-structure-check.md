ตรวจสุขภาพ structure ของ Hub — ขนาดไฟล์, consistency ระหว่าง CLAUDE.md/config/code, dependency drift

## วิธีใช้
```
/hub-structure-check
```

## ขั้นตอน

**1. ตรวจขนาด `app.py`:**
- จำนวนบรรทัด, ขนาดไฟล์ (KB)
- จำนวน function (`def `)
- function ที่ยาวเกิน 150 บรรทัด (candidate ที่ควรแยก)
- threshold: warn เมื่อไฟล์ > 500KB หรือมี function > 150 บรรทัด

**2. Consistency: `config.json` ↔ `CLAUDE.md`:**
- project_type ทุกตัวใน config.json ต้องมีในตาราง "Project Types" ของ CLAUDE.md
- ทุก stage ที่อ้างใน CLAUDE.md (Stage 1–9) ต้องมี handler ใน app.py (`@app.route('/api/run/<step>')`)
- duplicate project id หรือ path ที่ชนกัน

**3. Consistency: ตาราง Pipeline Stages ↔ code จริง:**
- เปิด `app.py` หา function `updatePipelineForType()` → อ่าน hidden stages ของแต่ละ type
- เทียบกับตารางใน CLAUDE.md (lines ที่มี ✓/—)
- รายงานถ้าไม่ตรง (เช่น กรณี manual-testing Stage 6)

**4. Dependency drift: `requirements.txt` ↔ imports + System Check probe:**
```bash
grep -hE '^\s*(import |from )' app.py | grep -oE '(import|from)\s+\w+' | awk '{print $2}' | sort -u
```
- เทียบ 3rd-party imports ที่เจอกับ `requirements.txt`
- กรอง stdlib ออก (sys, os, re, io, json, shutil, threading, time, subprocess, atexit, signal, zipfile, datetime, pathlib, smtplib, email, ฯลฯ)
- รายงาน packages ที่ใช้ใน code แต่ไม่อยู่ใน requirements (เช่น `resend`)
- รายงาน packages ใน requirements ที่ไม่มีใน code (dead deps)

**4b. System Check probe drift (สำคัญ):**
- หา function ใน `app.py` ที่ทำ Python Dependencies probe สำหรับ `/api/system-check` (ค้นด้วย `grep -n "Python Dependencies" app.py`)
- อ่าน list ของ modules ที่ probe (เช่น flask, openpyxl, docx, pandas, lxml, watchdog, dotenv)
- เทียบกับ `requirements.txt` — **ทั้ง 2 set ต้องตรงกัน** เพราะ: fresh clone → `pip install -r requirements.txt` → ต้องรัน System Check ผ่าน
- รายงาน modules ที่ System Check probe แต่ไม่มีใน requirements (= fresh install จะ fail)
- รายงาน modules ใน requirements แต่ไม่ได้ probe (อาจ OK ถ้าใช้ runtime only — flag ไว้พิจารณา)
- เทียบ CLAUDE.md L197 narrative กับ probe code — docs ต้องระบุครบ

**5. Hub-internal consistency:**
- ทุก slash command ที่ระบุใน CLAUDE.md (`/hub-status`, `/hub-diagnose`, ...) ต้องมีไฟล์จริงใน `.claude/commands/`
- ทุก scaffold type ใน CLAUDE.md ต้องมี folder จริงใน `scaffold/`
- ทุก endpoint ที่ระบุในตาราง API ต้องมี `@app.route(...)` ใน code

**6. แสดงผล:**
```
QA Hub Demo Structure Check — YYYY-MM-DD HH:MM
═══════════════════════════════════════════

📏 FILE SIZE
  app.py: 482 KB · 9,847 lines · 312 functions
  ⚠️  Large functions (>150 lines): 4
      - api_run_step (245 lines)
      - render_dashboard_html (189 lines)
      - ...

🔄 CONSISTENCY DRIFT
  ⚠️  CLAUDE.md table says manual-testing hides Stage 6
      → updatePipelineForType() shows Stage 6 enabled
      → Suggest: update CLAUDE.md OR revert code

  ⚠️  Project type "experimental" in config.json
      → Not documented in CLAUDE.md "Project Types" table

📦 DEPENDENCY DRIFT
  ❌ Missing in requirements.txt: resend (used line 603)
  ⚠️  Possibly unused: lxml (in requirements but no import found)

🔗 HUB INTERNAL
  ✅ All 4 slash commands have files
  ✅ All 2 scaffold types exist
  ⚠️  CLAUDE.md mentions /api/projects/discover but no @app.route found

✅ SUMMARY
  - 0 critical · 4 warnings · 1 missing dep
  - แนะนำ: แก้ dependency drift ก่อน (เสี่ยงสุดเวลา deploy)
```

## เมื่อไหร่ควรรัน
- **ก่อน release ทุกครั้ง** — จับ drift ที่อาจทำให้ deploy ล้ม (เช่น dep หาย)
- **หลังเพิ่ม feature ใหญ่** — ดูว่ามี consistency หลุดมั้ย
- **อย่างน้อยสัปดาห์ละครั้ง** — early warning, ไม่ปล่อยให้ drift สะสม

## ปรัชญา
ตาม **Goal-Driven Execution** — command นี้ถูกออกแบบเพื่อจับปัญหาที่**เคยเกิดจริง**ในโปรเจค ไม่ใช่ general-purpose linter:
- Check 3 + 4 = ROI สูงสุด (เคยเจอ bug แบบนี้แล้ว)
- Check 1 + 5 = early warning, ทำเป็นข้อมูลประกอบ
