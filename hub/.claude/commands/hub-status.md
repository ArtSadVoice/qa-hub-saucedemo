สรุปสถานะทุก project ใน Hub — type, phase, last run, pass rate, open bugs, release gate

## วิธีใช้
```
/hub-status              # ทุก project
/hub-status --active     # เฉพาะ active
```

## ขั้นตอน

**1. ตรวจว่า Hub รันอยู่:**
```bash
curl -s http://localhost:8080/api/projects
```
ถ้าไม่รัน → แจ้ง `❌ Hub ไม่ได้รัน — รัน python app.py ก่อน`

**2. ดึงข้อมูล:**
```bash
curl -s http://localhost:8080/api/summary
curl -s http://localhost:8080/api/projects
```

**3. แสดงตาราง:**
```
QA Hub Demo Status — YYYY-MM-DD HH:MM
═══════════════════════════════════════════════════════
Project               Type            Phase     Last Run    Pass%  Bugs  Gate
─────────────────────────────────────────────────────────────────────────────
BAY VoCSurvey         full-pipeline   active    2026-04-17  95%    0     ✅
KTB Masking           manual-testing  active    2026-04-15  80%    1H    ⚠️
CentralTops           full-pipeline   planning  —           —      —     ⏸️
─────────────────────────────────────────────────────────────────────────────
Active: 2/3  |  Ready: 1/2  |  Critical bugs: 0  |  High bugs: 1
```

Legend: ✅ READY  ⚠️ WARNING (High bug / pass<80%)  ❌ BLOCKED (Critical bug)  ⏸️ PLANNING/PAUSED
