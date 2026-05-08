ช่วย user เขียน requirement.md แบบ interactive สำหรับ BA Agent

## ขั้นตอน

**1. อ่าน context ของ project ก่อน:**
```
Read: CLAUDE.md   ← ดู App name, Base URL, stack ปัจจุบัน
```
ถ้ามีไฟล์ใน `requirements/` อยู่แล้ว → อ่านก่อนเพื่อต่อยอด ไม่ใช่เขียนทับทันที

**2. ถามข้อมูล (interactive) — ถามทีละกลุ่ม ไม่ถามทีเดียวทั้งหมด:**

กลุ่ม A — ข้อมูลพื้นฐาน:
- Feature / หน้าที่ต้องการ test คืออะไร?
- URL ของ app ที่ test (ถ้าต่างจาก CLAUDE.md)
- ผู้ใช้คือใคร (role / actor)?

กลุ่ม B — User Flow:
- ขอให้อธิบาย flow หลักทีละขั้นตอน (ภาษาพูดได้เลย)
- มี flow รอง / branch ไหม? (เช่น ถ้าเลือก A ไป flow นี้ / เลือก B ไป flow นั้น)

กลุ่ม C — Validation & Rules:
- field ไหนบ้างที่ required?
- มี format validation ไหม? (email, phone, number range)
- error message ที่แสดงเมื่อ validation fail คืออะไร? (ถ้ารู้)

กลุ่ม D — Edge Cases (ถามเฉพาะถ้า user ยังไม่ได้บอก):
- สิ่งที่ต้องทำก่อน test ได้ (pre-condition)?
- มี data ที่ test ต้องใช้ไหม? (test data)
- มี scenario พิเศษที่ต้อง test เป็นพิเศษไหม?

**3. Generate requirement.md** หลังได้ข้อมูลครบ:

สร้างในรูปแบบที่ BA Agent เข้าใจได้ดีที่สุด:

```markdown
# [Feature Name] — Requirement

## Overview
- **App**: [ชื่อ]
- **URL**: [URL]
- **Actor**: [ผู้ใช้]
- **Scope**: [สิ่งที่ต้อง test]

## User Flows

### Flow 1: [ชื่อ flow หลัก]
1. [ขั้นตอน 1]
2. [ขั้นตอน 2]
   - Expected: [ผลที่คาดหวัง]
3. [ขั้นตอน 3]
   - Expected: [ผลที่คาดหวัง]

### Flow 2: [ชื่อ flow รอง / alternative] (ถ้ามี)
...

## Validation Rules
- [Field A]: required / format: xxx / error message: "xxx"
- [Field B]: ...

## Edge Cases
- [กรณี 1]: [expected behavior]
- [กรณี 2]: [expected behavior]

## Pre-conditions
- [สิ่งที่ต้องมีก่อน test]

## Out of Scope
- [สิ่งที่ไม่ต้อง test ในรอบนี้]
```

**4. ให้ user review ก่อนบันทึก:**
- แสดง requirement.md ที่เขียนให้ดูก่อน
- ถามว่า "มีอะไรต้องเพิ่มหรือแก้ไขไหม?"
- ถ้า user OK → บันทึกไฟล์

**5. บันทึกไฟล์:**
```
Write: requirements/requirement.md
```
ถ้ามีไฟล์เดิมอยู่แล้ว → backup ก่อน: rename เป็น `requirements/requirement_backup_YYYYMMDD.md`

**6. แนะนำขั้นตอนถัดไป:**
```
✓ บันทึกแล้ว: requirements/requirement.md

ขั้นตอนถัดไป:
  /ba-agent          ← ให้ AI สร้าง TCM Excel จาก requirement นี้
  หรือเปิด Hub → Stage 2 → Run BA Agent
```

## หมายเหตุ
- ใช้ภาษาไทยตลอด ยกเว้น technical term
- ถ้า user paste ข้อมูลมาให้เยอะแล้ว → ไม่ต้องถามซ้ำ ให้ draft ได้เลย
- ถ้า $ARGUMENTS มีค่า → ใช้เป็นชื่อ feature เริ่มต้น เช่น `/write-req Survey Flow`
- ไม่ต้องสมบูรณ์ 100% — ดีกว่าไม่มีเลย BA Agent จะเติมส่วนที่ขาดได้
