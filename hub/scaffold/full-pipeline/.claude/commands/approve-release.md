ตรวจ release readiness ทุก gate แล้วสร้าง approval checklist พร้อม sign-off

## วิธีใช้

```
/approve-release              # ตรวจทุก gate และสร้าง approval record
/approve-release --check      # ตรวจ gate อย่างเดียว ไม่สร้าง record
/approve-release --notify     # ส่ง Slack notification หลัง approve
```

## ขั้นตอน

**1. ส่งงานให้ Release Approval Agent:**

```
ใช้ release-approval subagent
Args: $ARGUMENTS
```

**2. ผลลัพธ์ที่ได้:**

```
Release Approval — [Project Name]
══════════════════════════════════
Status: ✅ READY FOR APPROVAL

Gate: 8/8 passed

Approval record: docs/reviews/release_approval_20260418_143000.md
Slack notification: ส่งแล้ว (#qa-reports)

ขั้นตอนถัดไป:
  → ส่งไฟล์ docs/reviews/release_approval_20260418_143000.md ให้ QA Lead / PM sign-off
  → หลัง sign-off รัน /report-send เพื่อส่ง Word report ให้ทีม
```

หรือถ้าไม่ผ่าน:
```
Status: ❌ NOT READY — 2 blockers

Blockers:
  ❌ Pass Rate: 65% (ต้อง ≥ 80%) — รัน /test-tag @e2e และแก้ failures
  ❌ No High Bug: 2 open High bugs — ปิด bugs ก่อน release

Approval record: ไม่สร้าง (มี blockers)
```

## Approval Lifecycle

```
/approve-release
    ↓
Gate Check → ✅ READY → สร้าง approval record → QA Lead sign-off → APPROVED
                      ↘                                          ↘ REJECTED → แก้ไข
            ❌ NOT READY → แก้ blockers → รัน /approve-release ซ้ำ
```

## Integration กับ pipeline

รัน หลังจาก:
1. `/test-tag @e2e` หรือ `/test` ผ่าน
2. `/cross-review` รายงาน READY
3. `/excel-review-agent` ไม่มี Critical Issues

ก่อนที่จะ:
4. `/report-send` — ส่ง report ให้ทีม
5. Deploy to Production
