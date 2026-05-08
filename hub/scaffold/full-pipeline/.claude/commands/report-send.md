ส่ง Word report ให้ทีมงานผ่าน Email และ/หรือ Slack

## วิธีใช้

```
/report-send                    # ส่ง report ล่าสุดผ่านทั้ง email + Slack
/report-send --channel slack    # ส่งเฉพาะ Slack
/report-send --channel email    # ส่งเฉพาะ Email
/report-send output/MyReport.docx  # ระบุไฟล์
```

## ขั้นตอน

**1. ตรวจ configuration:**

อ่าน `docs/distribution.json`:
- `report_recipients` — รายชื่อ email ผู้รับ
- `slack_webhook` — Slack Incoming Webhook URL
- `smtp` — SMTP settings

ถ้าไม่พบ `docs/distribution.json` → แจ้ง:
```
⚠️ ไม่พบ docs/distribution.json
สร้างไฟล์และกรอก email/Slack ก่อนใช้คำสั่งนี้
```

**2. หา report ล่าสุดใน output/:**

ถ้าไม่ได้ระบุ path → ใช้ไฟล์ `output/*.docx` ที่แก้ล่าสุด

ถ้าไม่มีไฟล์ → แจ้ง `❌ ไม่พบ report ใน output/ — รัน /report ก่อน`

**3. รันสคริปต์:**

```bash
python scripts/send_report.py [report_path] [--channel <channel>]
```

**4. แสดงผล:**

```
📤 ส่ง report: ProjectName_TestResult_20260418.docx
   Channel: both

✅ Email ส่งถึง: qa@example.com, pm@example.com
✅ Slack notification ส่งไปที่ #qa-reports
```

## ตั้งค่าครั้งแรก

แก้ `docs/distribution.json`:
```json
{
  "report_recipients": ["qa@example.com", "pm@example.com"],
  "slack_webhook": "https://hooks.slack.com/services/...",
  "smtp": {
    "host": "smtp.gmail.com",
    "port": 587,
    "user": "your@gmail.com",
    "password": "app-password"
  }
}
```

> Gmail ต้องใช้ App Password (ไม่ใช่ password หลัก): myaccount.google.com → Security → App passwords
