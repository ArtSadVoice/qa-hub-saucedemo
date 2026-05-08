มอบหมาย bug ให้ทีมงานและส่ง notification ผ่าน Slack

## วิธีใช้

```
/bug-assign                        # แสดง open bugs ทั้งหมด แล้วให้เลือก assign
/bug-assign BUG-001 --to "ชื่อ"   # assign bug นั้นตรงๆ
/bug-assign --unassigned           # แสดงเฉพาะ bugs ที่ยังไม่มี assignee
```

## ขั้นตอน

**1. ดึง bug list จาก Hub:**
```bash
curl -s "http://localhost:8080/api/bugs?p=<project_id>"
```

ถ้า Hub ไม่รัน → อ่าน `docs/bugs.json` (local cache) แทน

**2. แสดง open bugs:**
```
Open Bugs — [Project Name]
══════════════════════════
ID       Severity  Title                        Assignee   Age
BUG-001  🔴 Critical  Submit button ไม่ตอบสนอง    —          3d
BUG-002  🟠 High     NPS score ไม่บันทึก          John       1d
BUG-003  🟡 Medium   UI ไม่แสดงเมื่อ screen < 375  —          5d
```

**3. รับ assignment จาก user:**

ถ้าไม่ได้ระบุ `--to` → ถาม:
```
Bug: BUG-001 — Submit button ไม่ตอบสนอง
Assign ให้ใคร? (ชื่อหรือ email ตาม docs/distribution.json):
```

**4. อัปเดต assignee ผ่าน Hub API:**

Hub เก็บ assignee ใน field `related_task` (เนื่องจาก Hub schema ไม่มี field `assignee` โดยตรง):
```bash
curl -s -X POST http://localhost:8080/api/bugs/update \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "<id>",
    "id": "<bug_id>",
    "related_task": "Assigned: <name> (<YYYY-MM-DD HH:MM>)"
  }'
```

ถ้า Hub ไม่รัน → แก้ไฟล์ `bugs/<project_id>.json` โดยตรง (เพิ่ม `"assignee": "<name>"` ในรายการ bug นั้น)

**5. ส่ง Slack notification (ถ้า slack_webhook ใน docs/distribution.json):**

อ่าน `docs/distribution.json` → field `slack_webhook`

```bash
curl -s -X POST "<slack_webhook>" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "🐛 Bug Assigned — [Project]\n*BUG-ID*: <bug_title>\n*Severity*: <severity>\n*Assigned to*: <name>\n*Link*: http://localhost:8080"
  }'
```

- ถ้า slack_webhook ว่าง → ข้ามขั้นตอนนี้ แจ้ง "Slack webhook ไม่ได้ตั้งค่า"

**6. แสดงผล:**
```
✅ BUG-001 assigned ให้ John
   Slack notification: ส่งแล้ว / ข้าม (ไม่มี webhook)
```

## ตั้งค่า

เพิ่ม slack_webhook และทีมงานใน `docs/distribution.json`:
```json
{
  "team": [{"name": "John", "email": "john@example.com", "role": "Dev"}],
  "slack_webhook": "https://hooks.slack.com/services/..."
}
```
