Trigger scheduled test run ผ่าน Hub API โดยไม่ต้องเปิด Hub UI

## วิธีใช้

```
/schedule-run                        # รัน all tests บน UAT
/schedule-run --tag @smoke           # รัน smoke tests บน UAT
/schedule-run --tag @e2e --env prod  # รัน e2e บน Prod (ขอ confirm ก่อน)
/schedule-run --action generate      # รัน generate TCM
/schedule-run --action inject        # รัน screenshot injection
```

## ขั้นตอน

**1. Pre-check: ตรวจว่า BASE_URL เข้าถึงได้** (เฉพาะ action=tests)

ถ้า `--action` เป็น `tests` หรือไม่ระบุ → อ่าน BASE_URL จาก `CLAUDE.md` แล้วรัน:
```bash
curl -s --max-time 10 -o /dev/null -w "%{http_code}" "$BASE_URL"
```
- HTTP 2xx/3xx → ✅ ผ่าน — รันต่อ
- timeout / HTTP 4xx 5xx → แจ้ง `❌ ENV Pre-check FAILED` และหยุด

**2. parse $ARGUMENTS:**
- `--tag` = `@smoke` | `@e2e` | `@regression` | `@visual` | `all` (default)
- `--env` = `uat` (default) | `prod`
- `--action` = `tests` (default) | `generate` | `inject`

**3. ถ้า env=prod และ tag≠@smoke → ขอ confirm:**
```
⚠️  กำลังจะ trigger [action] บน PROD ด้วย tag [tag]
แนะนำ @smoke only บน production
ยืนยันหรือไม่? (yes/no)
```

**4. ตรวจว่า Hub รันอยู่ไหม:**
```bash
curl -s http://localhost:8080/api/projects > /dev/null 2>&1
```
- ถ้า Hub ไม่ได้รัน → แจ้ง และเสนอรัน test โดยตรงแทน:
  ```bash
  TEST_ENV=<env> npx playwright test --grep "<tag>"
  ```

**5. ดึง project_id จาก CLAUDE.md หรือ config.json:**
- อ่าน `CLAUDE.md` — หา project name แล้ว slugify เป็น project_id
- หรืออ่าน Hub config: `GET http://localhost:8080/api/projects` แล้ว match ชื่อ

**6. Trigger run ผ่าน Hub API:**
```bash
curl -s -X POST http://localhost:8080/api/schedules/run-now \
  -H "Content-Type: application/json" \
  -d '{"project_id": "<id>", "action": "<action>", "tag": "<tag>", "env": "<env>"}'
```

**7. Poll ผลลัพธ์ทุก 5 วินาที (สูงสุด 3 นาที):**
```bash
curl -s "http://localhost:8080/api/schedules/notifications"
```
แสดง progress: `⏳ Running [action] [@tag] on [ENV]...`

**8. แสดงผลสรุปเมื่อเสร็จ:**
```
✅ Run complete — ENV: UAT | Tag: @smoke | Pass: 18 | Fail: 0
```
หรือถ้า fail:
```
❌ Run failed — ENV: UAT | Tag: @e2e | Pass: 15 | Fail: 3
   Flaky: TS_02_03 (retry 1)
```
