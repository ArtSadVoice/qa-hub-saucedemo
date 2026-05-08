อ่านไฟล์ที่วางไว้ใน `input/` หรือ `requirements/` แล้วสรุปเป็น `requirements/requirement.md` พร้อมส่งต่อ BA Agent ได้ทันที

## ขั้นตอน

**1. อ่าน context ของ project:**
```
Read: CLAUDE.md    ← App name, Base URL, stack
```

**2. สแกนหาไฟล์ input:**

ค้นหาตามลำดับนี้:
- `input/` → ไฟล์ `.xlsx`, `.md`, `.txt`, `.pdf`
- `requirements/` → ไฟล์ `.md`, `.xlsx`
- `figma/` → ไฟล์ `.png`, `.jpg` (Figma export)

ถ้ามีหลายไฟล์ → แสดงรายการให้ user เลือก  
ถ้าไม่มีไฟล์เลย → แจ้ง `"ไม่พบไฟล์ใน input/ หรือ requirements/ — วางไฟล์ก่อนแล้วรัน /summarize-input อีกครั้ง"`

ถ้า $ARGUMENTS มีค่า → ใช้ไฟล์นั้นโดยตรง เช่น `/summarize-input input/myfile.xlsx`

**3. อ่านและวิเคราะห์ไฟล์:**

สำหรับ **Excel (.xlsx)**:
- อ่านด้วย Read tool โดยตรง
- จับ: sheet names, column headers, row data
- มองหา: feature name, test scenarios, URL, actors, validation rules, expected results

สำหรับ **Markdown (.md) / Text (.txt)**:
- อ่านด้วย Read tool
- จับ: หัวข้อ, bullet points, flow descriptions, business rules

สำหรับ **รูปภาพ (.png/.jpg)**:
- อ่านด้วย Read tool (visual analysis)
- วิเคราะห์ UI elements: input fields, buttons, labels, error areas
- สกัด: flow จาก UI, selector hints จาก label/placeholder ที่เห็น

**4. สร้าง requirement.md:**

สรุปให้ได้รูปแบบที่ BA Agent (`/ba-agent`) นำไปใช้ต่อได้ทันที:

```markdown
# [Feature Name] — Requirement
> สรุปจาก: [ชื่อไฟล์ต้นทาง] · วันที่: [วันนี้]

## Overview
- **App**: [จาก CLAUDE.md]
- **URL**: [URL ที่พบ หรือจาก CLAUDE.md]
- **Actor**: [ผู้ใช้ที่พบในไฟล์]
- **Scope**: [สิ่งที่ต้อง test]

## User Flows

### Flow 1: [ชื่อ flow หลัก]
1. [ขั้นตอน]
   - Expected: [ผลที่คาดหวัง]

### Flow 2: [ชื่อ flow รอง] (ถ้ามี)
...

## Validation Rules
- [Field]: required / format: xxx / error: "xxx"

## Edge Cases & Business Rules
- [กรณี]: [expected behavior]

## Pre-conditions
- [สิ่งที่ต้องมีก่อน]

## Gaps / สิ่งที่ไม่ชัดเจน
- [ข้อมูลที่ไม่พบในไฟล์ — BA Agent จะถามเพิ่ม]

## Out of Scope
- [สิ่งที่ไม่ต้อง test รอบนี้ ถ้าระบุไว้]
```

**5. แสดงผลให้ user review:**
- แสดง requirement.md ที่สรุปได้
- บอก confidence: `"สกัดได้ครบ X% — ส่วนที่ขาดอยู่ใน Gaps"`
- ถาม: `"มีอะไรต้องแก้ไขหรือเพิ่มเติมไหม? (หรือพิมพ์ ok เพื่อบันทึก)"`

**6. บันทึกไฟล์:**

ถ้ามี `requirements/requirement.md` อยู่แล้ว → backup ก่อน:
```bash
# rename เป็น requirements/requirement_backup_YYYYMMDD_HHMMSS.md
```
จากนั้น Write ไฟล์ใหม่:
```
Write: requirements/requirement.md
```

**7. แนะนำขั้นตอนถัดไป:**
```
✓ บันทึกแล้ว: requirements/requirement.md

ขั้นตอนถัดไป:
  /ba-agent    ← AI สร้าง structured JSON + TCM Excel จาก requirement นี้
  /write-req   ← แก้ไข requirement แบบ interactive ก่อนส่ง BA Agent
```

## หมายเหตุ
- ถ้าไฟล์ Excel มีหลาย sheet → อ่านทุก sheet แล้วรวมข้อมูล
- ถ้าไฟล์มีข้อมูลมากและซับซ้อน → สรุปเฉพาะส่วนที่เกี่ยวกับ test scenario ไม่ต้อง copy ทั้งหมด
- section "Gaps" สำคัญมาก — BA Agent จะใช้ไปถามเพิ่มเพื่อเติมส่วนที่ขาด
- ใช้ภาษาไทยตลอด ยกเว้น technical term
