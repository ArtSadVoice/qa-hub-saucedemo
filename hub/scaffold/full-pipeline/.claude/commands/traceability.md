สร้าง Requirement ↔ Test Case ↔ Test Result traceability matrix

## วิธีใช้

```
/traceability            # สร้าง matrix จาก artifacts ปัจจุบัน
/traceability --save     # สร้างและบันทึก docs/reviews/traceability_YYYYMMDD.md
```

## ขั้นตอน

**1. รวบรวม artifacts:**
- `logs/ba_output_*.json` — ล่าสุด (BA requirements)
- `input/*.xlsx` — TCM Excel
- `tests/e2e/*.spec.ts` — Playwright specs
- `logs/playwright_results.json` — ผล test ล่าสุด (ถ้ามี)

ถ้า artifact ใดไม่พบ → แจ้งและดำเนินการต่อด้วย "N/A" สำหรับ column นั้น

**2. ส่งงานให้ QA Agent — MODE TRACEABILITY:**

```
ใช้ qa-agent subagent: MODE TRACEABILITY
Input: artifacts ที่รวบรวมได้ใน step 1
```

**3. Output ที่ต้องการ:**

```
TRACEABILITY MATRIX — [Project Name]
══════════════════════════════════════
Generated: YYYY-MM-DD

| Req ID | Scenario | TCID | Priority | Tag | Status | Spec File |
|--------|----------|------|----------|-----|--------|-----------|
| SC-001 | NPS happy path | TS_01_01 | P1 | @e2e | ✅ Pass | TS_01_survey.spec.ts |
| SC-002 | NPS invalid | TS_01_02 | P2 | @regression | ❌ Fail | TS_01_survey.spec.ts |

SUMMARY:
  Total Requirements : N
  Total Test Cases   : N
  Pass               : N (X%)
  Fail               : N (X%)
  Not Executed       : N

GAPS:
  ⚠️  [AC ที่ไม่มี TC mapping]
  ⚠️  [TC ที่ไม่มี spec]
  ⚠️  [Flaky tests]
```

**4. บันทึก (ถ้ามี --save หรือ $ARGUMENTS):**
```
docs/reviews/traceability_YYYYMMDD_HHMMSS.md
```

แจ้งผล: `✅ Traceability matrix บันทึกที่ docs/reviews/traceability_YYYYMMDD_HHMMSS.md`
