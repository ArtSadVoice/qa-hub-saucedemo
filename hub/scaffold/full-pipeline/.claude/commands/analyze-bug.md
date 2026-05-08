เรียก Bug Analyzer Agent วิเคราะห์ failure ล่าสุด → verdict + proposed fix + hand-off

## ขั้นตอน

**1. รับ argument:**
- ถ้า $ARGUMENTS = TCID (เช่น `TS_01_03`) → วิเคราะห์เฉพาะ test นั้น
- ถ้า $ARGUMENTS = spec file path → วิเคราะห์ทุก fail ใน file นั้น
- ถ้าไม่มี $ARGUMENTS → วิเคราะห์ทุก fail ใน run ล่าสุด

**2. หา latest run:**
```bash
ls -t logs/playwright_results.json 2>/dev/null
ls -t test-results/.last-run.json 2>/dev/null
```
- ถ้าไม่มีทั้ง 2 ไฟล์ → หยุดและแจ้ง "ไม่พบ run history — รัน /test ก่อน"

**3. Pre-check: มี fail จริงไหม:**
```python
# parse logs/playwright_results.json
# stats.unexpected + stats.flaky == 0 → no-op
```
- ถ้า `stats.unexpected == 0` และ `stats.flaky == 0` → return "ไม่พบ failed/flaky tests ใน run ล่าสุด — no-op"
- ถ้า `stats.flaky > 0` แต่ `unexpected == 0` → ระบุชัด "เจอ flaky N case — จะวิเคราะห์ flaky pattern"

**4. รวบรวม evidence ตาม STEP 1 ใน `.claude/agents/bug-analyzer.md`:**
- error message + stack จาก `tests[].results[].errors`
- failure screenshot path: `test-results/<test>/test-failed-*.png`
- trace: `test-results/<test>/trace.zip`
- spec file ที่ fail
- baseline: เช็ค `stats.flaky` field โดยตรง

**4.5. Staleness pre-check (STEP 1.5 ใน agent):**
- ถ้า project มี exploration map (เช่น `requirements/survey_map.md` — ดู CLAUDE.md ของ project)
```bash
stat -c %Y requirements/survey_map.md 2>/dev/null
git log -1 --format=%ct -- tests/e2e/<failed-spec>
```
- ถ้า map mtime < spec mtime หรือ > 7 วัน → flag เป็น argument ส่งให้ agent
- ถ้าไม่มี map → ข้าม pre-check นี้

**5. อ่าน context:**
```
Read: .claude/agents/bug-analyzer.md   ← agent protocol + 6 categories
Read: CLAUDE.md                          ← project context (cold-start, visual policy ถ้ามี)
Read: <spec file ที่ fail>
Read: logs/playwright_results.json (ตำแหน่ง errors)
```

**6. เรียก Bug Analyzer (Task tool, subagent_type=general-purpose) per failed test:**
ส่ง prompt ที่มี:
- TCID + spec path + line + tag
- error message + screenshot/trace path
- staleness flag (ถ้ามี)
- ประวัติ flaky/retry

agent จะตัดสิน category ตาม heuristic + เลือก Action

**7. รับ output → บันทึก `docs/reviews/bug_analysis_YYYYMMDD_HHMMSS.md`** (ตาม format ใน agent)

**8. แสดงสรุปบน terminal:**

```
🐛 Bug Analysis — N failure(s)

  TS_XX_XX  [CATEGORY]  high   → ACTION
  ...

📋 Hand-off:
  - X case → playwright-agent
  - Y case → qa-agent BUG_REPORT
  - Z case → MANUAL_CONFIRM (visual)
```

**9. ถ้ามี VISUAL_DRIFT verdict:**
- แสดง diff PNG path + 2 hypotheses
- ถาม user: "ตั้งใจ (update baseline) / ไม่ตั้งใจ (open bug) / ดู diff ก่อน"
- **ห้าม** auto `--update-snapshots`

**10. ถ้ามี SELECTOR + staleness flag:**
- แนะนำรัน `/explore $BASE_URL` ก่อน rerun /test
- ห้ามแนะนำ selector ใหม่จนกว่า exploration map จะ refresh

## หมายเหตุ
- ใช้ `/analyze-bug` หลัง `/test` ทุกครั้งที่มี fail — เร็วกว่าเปิด trace ทีละไฟล์
- ใช้ `/analyze-bug TS_01_03` เพื่อ focus 1 test
- Output ใน `docs/reviews/` เก็บ audit trail; cross-review จะ pick up เมื่อทำ release readiness
- ถ้า verdict ขัดกับสิ่งที่คุณคาด → บอก reason ผ่าน feedback เพื่อปรับ heuristic ใน `.claude/agents/bug-analyzer.md`
