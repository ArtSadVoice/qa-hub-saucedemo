เรียก PR Analyzer Agent วิเคราะห์ diff ปัจจุบัน → impacted feature, risk, run plan

## ขั้นตอน

**1. รับ argument:**
- ถ้า $ARGUMENTS = base ref (เช่น `main`, `origin/main`, commit SHA, tag) → ใช้เป็น base
- ถ้า $ARGUMENTS = `--staged` → diff เทียบ index (สำหรับ pre-commit)
- ถ้าไม่มี $ARGUMENTS → ใช้ `origin/main` เป็น base, แจ้งผู้ใช้ว่าใช้ default

**2. Pre-check git state:**
```bash
git rev-parse --is-inside-work-tree
git status --short
git rev-parse --abbrev-ref HEAD
```
- ถ้าไม่ใช่ git repo → หยุด แจ้ง "ไม่พบ git repository ใน working dir"
- ถ้า working tree dirty (มี uncommitted) + ไม่ใช่ `--staged` mode → เตือน: "มี uncommitted change — diff อาจไม่สะท้อน PR จริง" แล้วถาม yes/no ก่อนทำต่อ

**3. Delta check — เลี่ยง re-run ถ้า diff = 0:**
```bash
git diff --name-only <base>..HEAD
```
- ถ้า output ว่าง → return "no-op: diff = 0" แล้วหยุด (ตามกฎสากลข้อ 4 ใน pr-analyzer)

**4. อ่าน context ที่จำเป็น:**
```
Read: .claude/agents/pr-analyzer.md   ← agent protocol
Read: CLAUDE.md                        ← project context (host platform, tag policy, cold-start ถ้ามี)
Bash: git diff --stat <base>..HEAD
Bash: git diff --name-only <base>..HEAD
Bash: git log --oneline <base>..HEAD
```

**5. เรียก PR Analyzer Agent (Task tool, subagent_type=general-purpose):**

ส่ง prompt ที่มี:
- diff name list + stat
- commit log
- baseline pass rate (ดึงจาก `logs/playwright_results.json` field `stats.expected/unexpected/flaky`)
- TCM mapping (ถ้าต้องการ accurate gap detection — `input/*.xlsx` latest)

agent จะทำงานตาม STEP 1–6 ใน `.claude/agents/pr-analyzer.md`

**6. รับ output → บันทึกที่ `docs/reviews/pr_analysis_YYYYMMDD_HHMMSS.md`** (ตาม format ใน agent file)

**7. แสดงสรุปสั้นบน terminal:**
- Risk verdict + reason 1 บรรทัด
- Recommended run plan (numbered)
- Hand-off (next agent / command)

**8. ถ้า risk = HIGH:**
- เตือน: "⚠️ HIGH risk — แนะนำรัน /test เต็ม + warm-up ก่อน @regression ถ้า project มี cold-start (ดู CLAUDE.md)"
- ถาม yes/no ว่าจะ trigger /test ต่อทันทีไหม

ถ้า risk = MED → แนะนำ run plan ที่ scope แคบ (`/test-tag @smoke` + `/test-file <changed>`)
ถ้า risk = LOW → แค่แจ้ง ไม่ต้องรัน

## หมายเหตุ
- ใช้ `/analyze-pr origin/main` ก่อนทุก PR เพื่อตัด CI time
- ถ้าแก้ host platform (ดู CLAUDE.md ของ project) — agent จะอ้าง constraints และเตือนเรื่อง restart/reload
- ถ้าแก้ requirement → agent จะแนะนำให้รัน `/ba-agent` ก่อน /test (TCM stale)
- output ใน `docs/reviews/` มี timestamp — เก็บเป็น audit trail สำหรับ release review
