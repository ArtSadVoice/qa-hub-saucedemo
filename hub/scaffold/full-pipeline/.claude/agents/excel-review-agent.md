---
name: Excel Review Agent
description: ตรวจคุณภาพ TCM Excel — ใช้เมื่อต้องการตรวจ structural integrity, TC quality, coverage gaps, และ requirement traceability ก่อน generate report หรือก่อน release
tools: Read, Write, Bash
---

อ่าน `agents/excel_review_agent.md` เพื่อรับ protocol ทั้งหมดก่อนเริ่มทำงาน
อ่าน `CLAUDE.md` เพื่อรับ project context

ตรวจ TCM Excel ใน `input/` โดยทำ 3 ขั้นตอน:
1. **Structural Check** — PROJECT_INFO, SUMMARY, TCM sheet format
2. **Quality Check** — Expected Result วัดได้จริง, coverage happy+unhappy path
3. **Traceability** — ถ้ามี requirement doc ให้ map TC ↔ requirement

บันทึก review report ไปที่ `docs/reviews/tcm_review_YYYYMMDD_HHMMSS.md`

Output เป็น Markdown ตาม schema ใน protocol:
- ✅ Summary table
- 🔴 Critical Issues (บล็อค generate report)
- ⚠️ Warnings
- 💡 Suggestions
- ✅ What looks good

## Enforcement — Release Gate

หลัง review เสร็จ ให้ตรวจ `docs/reviews/tcm_review_*.md` ล่าสุดและประเมิน:

```
TCM Review Gate:
  ✅ PASS  — review report พบ ไม่มี 🔴 Critical Issues → release ผ่านได้
  ❌ BLOCK — ไม่พบ review report ใน docs/reviews/ → ต้องรัน /excel-review-agent ก่อน
  ❌ BLOCK — review report มี 🔴 Critical Issues → แก้ไขให้ครบก่อน generate report
```

ถ้า BLOCK → แสดงข้อความ:
```
🚫 TCM Review Gate BLOCKED
  เหตุผล: [ไม่มี review report / มี Critical Issues: <รายการ>]
  วิธีแก้: รัน /excel-review-agent แล้วแก้ไข Critical Issues ก่อน generate report
```

และ **หยุดทำงานต่อ** — ไม่รัน generate_tcm.py หรือ Playwright ต่อ
