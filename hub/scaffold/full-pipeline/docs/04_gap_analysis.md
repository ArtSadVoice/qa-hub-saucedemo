# Gap Analysis & Recommendations
# สิ่งที่ขาดและแนะนำเพิ่มใน Agentic Loop

---

## 1. สิ่งที่มีอยู่แล้ว (ดีมาก ✅)

| มีแล้ว | อยู่ที่ |
|--------|--------|
| Excel TCM schema ที่ชัดเจน | CLAUDE.md |
| Word template พร้อม placeholder | template/ |
| generate_report.py + run.py | scripts/ |
| watch.py (auto re-generate) | scripts/ |
| diff + snapshot system | .snapshot.json |
| Status color coding | CLAUDE.md |
| Archive + backup system | archive/ |

---

## 2. สิ่งที่ขาดและควรเพิ่ม

### 🔴 Critical (ขาดแล้วกระทบ pipeline หลัก)

**A. Confidence Gate + Human Approval Step**
```
ปัญหา: BA Agent อาจ generate test case ผิดถ้า requirement ไม่ครบ
แก้:   เพิ่ม interactive prompt ใน orchestrator.py ก่อนรัน Stage 2
       "BA วิเคราะห์ได้ 23 scenarios, confidence 0.85 — proceed? (y/n)"
```

**B. Screenshot Auto-Attach ใน Word**
```
ปัญหา: ปัจจุบัน QA ต้องแนบ screenshot ใน Word เอง (manual)
แก้:   เพิ่ม screenshot_injector.py ที่:
       - อ่าน screenshots/[TCID].png
       - หา placeholder "[แนบ Screenshot/Evidence สำหรับ TS_XX]" ใน Word
       - inject รูปลงตำแหน่งนั้นด้วย python-docx
```

**C. Playwright Config File**
```
ปัญหา: ยังไม่มี playwright.config.ts ใน project
แก้:   สร้าง playwright.config.ts กำหนด baseURL, timeout, screenshot path
       ให้ชี้ไปที่ screenshots/ directory
```

---

### 🟡 Important (ทำให้ pipeline สมบูรณ์ขึ้นมาก)

**D. Notification Agent**
```
ปัญหา: QA ไม่รู้ว่า pipeline เสร็จหรือ test fail
แก้:   เพิ่ม notify.py ส่ง Line Notify หรือ Slack เมื่อ:
       - Pipeline เสร็จ (summary pass/fail count)
       - Confidence < 0.7 (ต้องการ clarification)
       - Test fail > threshold (เช่น > 20%)

# ตัวอย่าง Line Notify
import requests
def notify_line(message: str):
    requests.post(
        "https://notify-api.line.me/api/notify",
        headers={"Authorization": f"Bearer {os.getenv('LINE_NOTIFY_TOKEN')}"},
        data={"message": message}
    )
```

**E. Diff + Audit Trail**
```
ปัญหา: ไม่รู้ว่า BA Agent เปลี่ยนอะไรระหว่าง run
แก้:   เก็บ ba_output JSON ทุก run ใน logs/
       เพิ่ม diff viewer: "เปรียบเทียบ run นี้กับครั้งที่แล้ว"
       → แสดง scenario ที่เพิ่ม/ลด/เปลี่ยน
```

**F. Test Data Seeding**
```
ปัญหา: Playwright test ต้องการ test data ใน DB (user accounts, products)
แก้:   เพิ่ม seed.py ที่รันก่อน Playwright:
       - สร้าง test accounts
       - สร้าง seed data ที่ BA Agent ระบุใน "test_data" field
       - cleanup หลัง test เสร็จ
```

**G. Requirement Version Control**
```
ปัญหา: ไม่รู้ว่า requirement เปลี่ยนอะไรระหว่าง sprint
แก้:   เก็บ requirement input ทุกครั้งที่รัน pipeline
       ไว้ใน requirements/[sprint]/[feature]_YYYYMMDD.md
       เปรียบเทียบกับ sprint ก่อนหน้าได้
```

---

### 🟢 Nice to Have (ทำได้ในอนาคต)

**H. Multi-Feature Pipeline**
```
ปัญหา: orchestrator.py รัน 1 feature ต่อครั้ง
แก้:   รองรับ requirements/ directory ที่มีหลายไฟล์
       รัน parallel ได้ด้วย asyncio
```

**I. Figma MCP Integration**
```
ปัญหา: ตอนนี้ Figma ใช้ screenshot เท่านั้น
แก้:   ถ้า Claude Code เชื่อมต่อ Figma MCP แล้ว
       BA Agent เรียก figma_get_file tool ได้โดยตรง
       ได้ component name + variant + interaction โดยไม่ต้อง export PNG
```

**J. PDF Export อัตโนมัติ**
```
ปัญหา: QA ต้อง export Word → PDF เอง
แก้:   เพิ่ม libreoffice CLI conversion:
       libreoffice --headless --convert-to pdf output/*.docx
```

**K. Test Coverage Report**
```
เพิ่ม coverage_report.py ที่สรุป:
- จำนวน requirement → scenarios → TC
- % coverage ของแต่ละ feature
- scenario ที่ยังไม่มี test
```

---

## 3. Priority Roadmap

```
Sprint 1 (ทำก่อน — critical):
  ✅ orchestrator.py (done)
  ✅ ba_agent.md (done)
  ✅ qa_agent.md (renamed + upgraded from test_case_agent.md)
  ✅ playwright_agent.md (done)
  [ ] playwright.config.ts
  [ ] Confidence gate interactive prompt

Sprint 2 (สำคัญ):
  [ ] screenshot_injector.py (auto-attach ใน Word)
  [ ] notify.py (Line/Slack notification)
  [ ] Audit trail (log + diff ระหว่าง run)

Sprint 3 (เสริม):
  [ ] Test data seeding
  [ ] Requirement version control
  [ ] PDF auto-export
```

---

## 4. ข้อควรระวัง

| ความเสี่ยง | ผลกระทบ | ป้องกัน |
|------------|---------|---------|
| BA Agent confidence ต่ำ → test case ผิด | ทำงานซ้ำ | Confidence gate + human review |
| Playwright selector เปลี่ยนตาม UI update | Test fail ทุก sprint | ใช้ data-testid เป็นหลัก |
| orchestrator.py overwrite TCM ที่ QA กรอกแล้ว | สูญเสีย data | ตรวจไฟล์ก่อน เพิ่ม --force flag |
| API rate limit (ถ้ารัน หลาย feature) | Pipeline หยุดกลางคัน | เพิ่ม retry + exponential backoff |
| Figma screenshot ขาดข้อมูล business rule | AC ไม่ครบ | ต้องมี requirement doc ประกอบเสมอ |
