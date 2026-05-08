Run the BA Agent inline using Claude Code — ไม่ต้องใช้ ANTHROPIC_API_KEY

## ขั้นตอน

**1. หา requirement input:**
- ถ้ามี $ARGUMENTS → ใช้ไฟล์นั้น (เช่น `/ba-agent requirements/my_req.md`)
- ถ้าไม่มี → หา latest `.md` ใน `requirements/` อัตโนมัติ
- ถ้ามีไฟล์ `.png` ใน `figma/` → แนบเป็น visual context ด้วย

**1b. Figma MCP (ถ้ามี figma_url ใน CLAUDE.md):**
- อ่าน CLAUDE.md — ถ้ามี `figma_url:` → ใช้ Figma MCP tools ดึง design data
- `get_file(figma_url)` → โครงสร้าง frames + components ทั้งหมด
- `get_images(figma_url, node_ids)` → screenshot แต่ละ screen หลัก
- นำ design data มาประกอบกับ requirement file เพื่อวิเคราะห์ครบถ้วน
- ถ้าไม่มี figma_url → ข้ามขั้นตอนนี้ได้เลย

**2. อ่าน context ที่จำเป็น:**
```
Read: agents/ba_agent.md        ← BA Agent protocol
Read: CLAUDE.md                 ← project context (URL, stack, figma_url)
Read: <requirement file>        ← input
```

**3. วิเคราะห์ตาม BA Agent protocol** (จาก agents/ba_agent.md):
- Detect format (prose / user story / structured / Figma)
- สกัด: feature name, module, actors, acceptance criteria (Given/When/Then)
- สร้าง acceptance_criteria array ครบทุก happy path + unhappy path + edge case
- คำนวณ confidence_score (0.0–1.0)
- ถ้า confidence < 0.7 → แสดง clarifications_needed แล้วถามก่อนดำเนินการต่อ

**4. สร้าง ba_output JSON** ตาม schema:
```json
{
  "meta": {
    "feature_id": "QAHUB_XXX_001",
    "feature_name": "...",
    "module": "...",
    "priority": "high|medium|low",
    "actors": [...],
    "confidence_score": 0.9
  },
  "acceptance_criteria": [
    {
      "tsid": "TS_01",
      "tcid": "TS_01_01",
      "scenario_name": "...",
      "type": "happy_path|unhappy_path|edge_case",
      "given": "...",
      "when": "...",
      "then": {
        "visible_text": "...",
        "url": "",
        "state": ""
      },
      "selector_hints": [...]
    }
  ],
  "clarifications_needed": []
}
```

**5. บันทึก ba_output JSON:**
```bash
# บันทึกไปที่ logs/ba_output_YYYYMMDD_HHMMSS.json
```
Write ไฟล์ JSON ด้วย timestamp ปัจจุบัน

**6. รัน orchestrator ต่อจาก Stage 2 (TCM generation):**
```bash
python -X utf8 scripts/orchestrator.py --skip-ba logs/ba_output_<timestamp>.json --skip-playwright
```

**7. แสดงสรุปผล:**
- จำนวน TS และ TC ที่สร้าง
- ชื่อไฟล์ Excel ที่ generate
- Confidence score
- ถ้ามี clarifications_needed → แสดงคำถามให้ user ตอบ

## หมายเหตุ
- ไม่ต้อง ANTHROPIC_API_KEY — ใช้ Claude Code session ปัจจุบัน
- ถ้า `scripts/orchestrator.py --skip-ba` fail → ให้ดู error แล้วแก้ไขก่อน rerun
- Excel ที่ได้อยู่ที่ `input/` — ตรวจสอบด้วย `/status` หรือ Hub
