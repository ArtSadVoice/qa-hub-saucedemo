ตรวจหาปัญหาใน Hub — config, schedules, log errors, ghost runs, stale projects, critical bugs

## วิธีใช้
```
/hub-diagnose
```

## ขั้นตอน

**1. ตรวจว่า Hub รันอยู่:**
```bash
curl -s http://localhost:8080/api/projects
```

**2. ตรวจ config.json:**
- projects ที่ path ไม่พบในระบบ (orphan config)
- projects ที่ type ไม่ถูกต้อง (ไม่ใช่ full-pipeline / manual-testing / playwright-only)
- duplicate project id

**3. ตรวจ schedules:**
```bash
curl -s http://localhost:8080/api/schedules
```
- schedules ที่ enabled แต่ project ไม่ active
- schedules Prod + non-@smoke (เสี่ยง)
- last_status = error

**4. ตรวจ schedule.log:**
อ่าน `schedule.log` 100 บรรทัดล่าสุด → หา ERROR / TIMEOUT

**5. ตรวจ ghost runs:**
```bash
curl -s "http://localhost:8080/api/run/history?p=<id>"
```
- runs ที่ pass=0 & fail=0 (ghost)
- projects ที่ไม่ได้รัน test > 7 วัน

**6. ตรวจ critical bugs:**
```bash
curl -s "http://localhost:8080/api/bugs?p=<id>"
```
- open Critical / High bugs ทุก project

**7. แสดงผล:**
```
QA Hub Demo Diagnose — YYYY-MM-DD HH:MM
═══════════════════════════════════

🔴 CRITICAL (ต้องแก้ทันที)
  - [project] schedule "daily @e2e prod" เสี่ยง — แนะนำ @smoke only บน prod

⚠️  WARNINGS
  - [project] path ไม่พบ: /path/to/project
  - [project] ไม่ได้รัน test 12 วันแล้ว (last: 2026-04-05)
  - [project] มี 3 ghost runs — แนะนำ /purge

✅ OK
  - Config: 5 projects registered
  - Schedules: 2 active, 0 errors
  - Bugs: 0 Critical, 1 High (KTB Masking)
```
