รัน Playwright tests ตาม tag และ environment ที่ระบุ

## วิธีใช้

```
/test-tag @smoke           # รัน smoke tests บน UAT (default)
/test-tag @e2e             # รัน e2e tests บน UAT
/test-tag @regression      # รัน regression tests บน UAT
/test-tag @smoke --env prod  # รัน smoke tests บน Prod
/test-tag @visual          # รัน visual tests บน UAT
```

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
    BASE_URL: <url>  ENV: <env>
    Error: <timeout / HTTP <code>>
    แก้ไข: ตรวจสอบ BASE_URL และ network ก่อนรัน test
  ```

**2. parse arguments จาก $ARGUMENTS:**
- tag = `@smoke` | `@e2e` | `@regression` | `@visual` | (ถ้าไม่ระบุ = all)
- env = `uat` (default) | `prod`

**3. ถ้า env = prod และ tag ≠ @smoke → แจ้งเตือนและขอ confirm ก่อน:**
```
⚠️  กำลังจะรัน [tag] บน PROD — แนะนำ @smoke only บน production
ยืนยันหรือไม่? (yes/no)
```

**4. รัน test:**
```bash
TEST_ENV=<env> npx playwright test --grep "<tag>" --reporter=list
```

**5. แสดงผลลัพธ์:**
- ตาราง TCID | Name | Tag | ENV | Status | Duration
- สรุป: X/Y passed — ENV: [UAT/PROD] — Tag: [tag]
- Flaky tests (pass หลัง retry): แสดงแยกพร้อม retry count
- ถ้ามี flaky ≥ 3 runs → แสดง ⚠️ Flaky Blocker

**6. บันทึก ENV ลง run_history** (ถ้า Hub รันอยู่ใช้ POST /api/run/log):
```json
{ "env": "<env>", "tag": "<tag>", "pass": N, "fail": N, "flaky": N }
```
