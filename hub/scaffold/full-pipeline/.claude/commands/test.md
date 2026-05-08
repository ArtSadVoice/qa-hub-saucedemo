รัน Playwright tests ทั้งหมด แล้วสรุปผล

## ขั้นตอน

**1. Pre-check: ตรวจว่า BASE_URL เข้าถึงได้**

อ่าน BASE_URL จาก `CLAUDE.md` หรือ `tests/e2e/constants.ts` แล้วรัน:
```bash
curl -s --max-time 10 -o /dev/null -w "%{http_code}" "$BASE_URL"
```

- HTTP 2xx/3xx → ✅ ENV reachable — รันต่อ
- ไม่ได้รับ response / timeout / HTTP 4xx 5xx → หยุดและแจ้ง:
  ```
  ❌ ENV Pre-check FAILED
    BASE_URL: <url>
    Error: <timeout / HTTP <code>>
    แก้ไข: ตรวจสอบ BASE_URL ใน CLAUDE.md หรือ network connection ก่อนรัน test
  ```

**2. รัน tests:**
```bash
TEST_ENV=uat npx playwright test --reporter=list
```

แสดงตาราง TCID | Name | Tag | Status (✓/✘) | Duration
สรุป: "X/Y passed — ENV: UAT"

ถ้ามี failures → วิเคราะห์ว่าเป็น app bug หรือ selector issue
ถ้ามี flaky tests (pass หลัง retry) → แสดงแยกพร้อม ⚠️ ถ้า flaky ≥ 3 runs

> รัน tag เฉพาะ หรือ env อื่น ใช้ `/test-tag @smoke --env prod`
