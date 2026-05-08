# CLAUDE.md — QA Test Result Automation

> **วัตถุประสงค์:** ไฟล์นี้บอก Claude Code ว่า project นี้คืออะไร, โครงสร้างไฟล์เป็นอย่างไร,
> และต้องทำอะไรเมื่อได้รับคำสั่งจาก QA

---

## 📁 โครงสร้าง Project

```
qa-test-result/
│
├── CLAUDE.md                          ← ไฟล์นี้ (อ่านก่อนทำทุกครั้ง)
│
├── templates/
│   ├── Test_Case_Template.xlsx      ← Template Excel (INPUT หลัก — กรอกข้อมูล Test)
│   └── Test_Result_Template.docx      ← Template Word  (โครงสร้างรายงาน + header/footer)
│
├── input/
│   └── [ProjectName]_TestCase.xlsx    ← ไฟล์ TCM จริงที่ QA กรอกผลทดสอบ
│
├── output/
│   └── [ProjectCode]_TestResult_YYYYMMDD.docx  ← ไฟล์ที่ generate ออกมา
│
├── scripts/
│   ├── generate_report.py             ← Script หลักสำหรับ generate Word จาก Excel
│   ├── run.py                         ← One-shot: รันครั้งเดียว diff + generate แล้วจบ (แนะนำ)
│   ├── watch.py                       ← Daemon: ตรวจ input/*.xlsx อัตโนมัติ re-generate เมื่อมีการเปลี่ยนแปลง
│   ├── build_template.cjs             ← Node.js script สำหรับ generate Word จาก scratch (docx npm)
│   └── update_template.py             ← Script อัปเดต Template เมื่อมีการแก้ไข
│
└── archive/
    └── [เก็บไฟล์ output เก่า + backup ก่อน overwrite]
```

---

## 🗂️ โครงสร้างไฟล์ Excel Template

ไฟล์ `Test_Case_Template.xlsx` มี **3 sheets** ดังนี้:

### Sheet 1: `PROJECT_INFO`
ข้อมูลโปรเจกต์และผู้ Sign-off — **กรอกก่อนสร้างรายงานทุกครั้ง**

| Field (Column B) | ค่า (Column C) | หมายเหตุ |
|---|---|---|
| Project Code | `BRS CPALL (DCPS)` | ตัวอย่าง |
| Project Name | `BRS CPALL (DCPS)` | |
| Topic | `UAT Sign-Off` | |
| Customer | `The BRS Company` | |
| Prepared By | ชื่อ QA | เซลล์สีเหลือง = ต้องกรอก |
| Prepared Date | `DD MMM YYYY` | เช่น `23 Mar 2026` |
| Sprint / Version | `Sprint 1` | |
| Document List | `ProjectName_TestResult.pdf` | |

Sign-off persons อยู่ใน rows ถัดไป (Columns B–F):
`Role | Name | Position | Company | Date`

### Sheet 2: `SUMMARY`
**ห้ามแก้ไข manually** — ค่า Pass/Fail คำนวณอัตโนมัติจาก sheet TCM ด้วย `COUNTIFS`

| Column | ความหมาย |
|---|---|
| TSID | รหัส Test Scenario (TS_01 ถึง TS_08) |
| Test Scenario Description | ชื่อ Scenario |
| No. Test Cases | จำนวน TC ทั้งหมด |
| Pass / Fail / In-Progress / Block / Cancel / Not Start | นับจาก TCM อัตโนมัติ |
| Accuracy % | คำนวณจาก Pass/Total |

**Charts ใน sheet SUMMARY (v1.4):**

| Chart | ประเภท | Data range | Series |
|---|---|---|---|
| chart[0] | **PieChart** | `D5:J12` | No.TC, Pass, Fail, In-Progress, Block, Cancel, Accuracy % แยกตาม TS |
| chart[1] | **BarChart** | `D5:F13` | No.TC, Pass, Fail แยกตาม TS_01–TS_08 + TOTAL |

> Charts อยู่ใน Excel เท่านั้น — generate_report.py อ่านเฉพาะข้อมูลจาก `input/` ไม่ได้ embed chart ลง Word
> ถ้าต้องการ chart ใน Word ต้องทำ manual (copy จาก Excel แล้ว paste เป็น image ใน Word)

### Sheet 3: `TCM` (Test Case Matrix)
**ตารางหลักที่ QA กรอกผลทดสอบ** — เซลล์สีเหลือง = บังคับกรอก

| Column | ชื่อ | หมายเหตุ |
|---|---|---|
| A | TSID | `TS_01` ถึง `TS_08` — กรอกเฉพาะแถวแรกของแต่ละ Group |
| B | Test Scenario Description | กรอกเฉพาะแถวแรกของแต่ละ Group |
| C | TCID | เช่น `TS_01_01`, `TS_01_02` |
| D | Pre-condition | เงื่อนไขก่อนทดสอบ (ถ้ามี) |
| E | Test Data | ข้อมูลที่ใช้ทดสอบ (ถ้ามี) |
| F | Test Case Description | ชื่อ Test Case (ภาษาไทยหรืออังกฤษ) |
| G | Test Steps | ขั้นตอนการทดสอบ |
| H | Expected Result | ผลลัพธ์ที่คาดหวัง |
| I | P/N | `P` = Positive, `N` = Negative |
| J | **Status** | `Pass` / `Fail` / `In-progress` / `Block` / `Cancel` / `Not Start` |
| K | **Executed Date** | วันที่รัน Test เช่น `23 Mar 2026` |
| L | Remark | หมายเหตุเพิ่มเติม (ถ้ามี) |

---

## 📋 โครงสร้างไฟล์ Word Template

ไฟล์ `Test_Result_Template.docx` มีโครงสร้างดังนี้:

```
[Header]  ← Logo รูปภาพ (word/media/image1.png) แสดงทุกหน้า
─────────────────────────────────────────────────────────
Sign-off Acceptance Form          ← หน้า 1: ข้อมูลโปรเจกต์ + ลายเซ็น
Contents                          ← สารบัญอัตโนมัติ (SDT/TOC — Word update เมื่อเปิด)
1. Purpose                        ← วัตถุประสงค์
2. Application Overview           ← ภาพรวมระบบ
3. Test Scope                     ← ขอบเขตการทดสอบ
4. Test Scenarios                 ← ตาราง Summary (Pass/Fail/Accuracy)
5. Test Result                    ← ตาราง TC แยกตาม TS + Screenshot
   TS_01: [Scenario Name]
   TS_02: [Scenario Name]
   ...
6. Type of Testing Performed      ← ประเภทการทดสอบ
7. Exit Criteria                  ← เกณฑ์การผ่าน
─────────────────────────────────────────────────────────
[Footer]  ← Copyright & Page Number แสดงทุกหน้า
```

### โครงสร้าง ZIP ของ Template (สำคัญ — อย่าทำให้เสีย)

```
word/document.xml           ← body หลัก (8 tables + TOC SDT + placeholders)
word/styles.xml             ← styles (Heading1, Heading2 ต้องไม่ซ้ำ)
word/header1.xml            ← header template (logo image)
word/footer1.xml            ← footer template (copyright + page number)
word/_rels/header1.xml.rels ← rel สำหรับ image ใน header
word/media/image1.png       ← Logo image
word/settings.xml
word/numbering.xml
```

### Body index map (ใช้อ้างอิงใน generate_report.py)

| Index (body) | ประเภท | python-docx T# | รายละเอียด |
|---|---|---|---|
| [00] | TABLE 1×1 | T0 | Sign-off header |
| [02] | TABLE 8×2 | T1 | Project details (PROJECT_INFO) |
| [05] | TABLE 4×2 | T2 | Sign-off persons |
| [08] | **SDT** | — | **Table of Contents (อย่าแตะ — ไม่นับเป็น table)** |
| [17] | TABLE 9×9 | T3 | Summary (Section 4) |
| [24] | TABLE 4×6 | T4 | TS_01 partial rows |
| [31] | TABLE 3×6 | T5 | TS_02 partial rows |
| [38] | TABLE 5×2 | T6 | Type of Testing |
| [41] | TABLE 4×2 | T7 | Exit Criteria |

> **หมายเหตุ TOC:** เป็น `<w:sdt>` ไม่ใช่ `w:tbl` → python-docx `doc.tables[]` ไม่นับ → T0–T7 คงเดิม
> Word จะ update page numbers ของ TOC อัตโนมัติเมื่อเปิดไฟล์

### Evidence Placeholders (ใน Template + auto-generate จาก script)

แต่ละ TS section มี paragraph สำหรับ screenshot/evidence โดย script จะ **auto-generate** จาก TCID ใน Excel:
```
[แนบ Screenshot/Evidence สำหรับ TS_01]
TS_01_01  ตรวจสอบคำถาม Section "เริ่มแบบสอบถาม"
TS_01_02  ตรวจสอบคำถาม Section "RD"
TS_01_03  ตรวจสอบคำถาม Section "A"
...
```
Section 4 (Test Scenarios) ก็มี evidence placeholder เช่นกัน (มาจาก template โดยตรง):
```
[แนบ Screenshot/Evidence สำหรับ Test Scenarios]
```

Format: italic, 9pt, สีเทา `#595959`
> QA แนบ screenshot ด้วยตนเองใน Word โดยอ้างอิง TCID จาก paragraph นี้

> **⚠️ อย่า replace `templates/Test_Result_Template.docx` ด้วยไฟล์ที่ generate ออกมา**
> ถ้า template เสียหาย ให้ restore จาก `archive/Test_Result_Template_v1_backup.xlsx`

### Placeholder ที่ใช้ใน Template Word

| Placeholder | แทนด้วย |
|---|---|
| `{{PROJECT_CODE}}` | Project Code จาก PROJECT_INFO |
| `{{PROJECT_NAME}}` | Project Name จาก PROJECT_INFO |
| `{{TOPIC}}` | Topic จาก PROJECT_INFO |
| `{{CUSTOMER}}` | Customer จาก PROJECT_INFO |
| `{{PREPARED_BY}}` | ชื่อ QA จาก PROJECT_INFO |
| `{{PREPARED_DATE}}` | วันที่ Prepare จาก PROJECT_INFO |
| `{{SPRINT_VERSION}}` | Sprint/Version จาก PROJECT_INFO |
| `{{DOCUMENT_LIST}}` | Document List จาก PROJECT_INFO |
| `{{VENDOR_COMPANY}}` | ชื่อบริษัท Vendor |
| `{{CUSTOMER_COMPANY}}` | ชื่อบริษัท Customer |

---

## 🎯 Test Scenarios ที่รองรับ

| TSID | Scenario | จำนวน TC |
|---|---|---|
| TS_01 | Survey UI/UX | 10 |
| TS_02 | Survey flow and logic | 11 |
| TS_03 | Validation input | 3 |
| TS_04 | End-to-End | 3 |
| TS_05 | Email daily | 3 |
| TS_06 | Survey response | 3 |
| TS_07 | Responsive Mobile, Tablet | 2 |
| TS_08 | Verify unique link | 4 |
| **TOTAL** | | **39** |

> หากเพิ่ม/ลด Scenario ใหม่ ให้อัปเดต Section "Test Scenarios" ใน CLAUDE.md นี้ด้วย

---

## 🤖 คำสั่งที่ Claude Code รองรับ

### คำสั่งที่ 1: Generate Test Result Word จาก Excel

**เมื่อ QA พิมพ์ว่า:**
> "generate report" หรือ "สร้างรายงาน" หรือ "สร้าง Word จาก Excel"

**Claude Code ต้องทำ:**

```python
# 1. อ่าน PROJECT_INFO จาก templates/Test_Case_Template.xlsx
# 2. อ่าน TCM data (TSID, TCID, Description, Expected, P/N, Status, Date)
# 3. คำนวณ Summary (Pass/Fail/Total per TSID)
# 4. โหลด templates/Test_Result_Template.docx
# 5. แทน {{placeholder}} ทั้งหมดด้วยข้อมูลจริง
# 6. เติมตาราง Section 4 (Test Scenarios Summary)
# 7. เติมตาราง Section 5 (Test Result per TS) จาก TCM
# 8. บันทึกเป็น output/[ProjectName]_TestResult_[YYYY-MM-DD].docx
```

**ชื่อไฟล์ output:** `[ProjectCode]_TestResult_YYYYMMDD.docx`
เช่น `BRS_CPALL_DCPS_TestResult_20260323.docx`

---

### คำสั่งที่ 2: อัปเดต Status ใน Excel แล้ว Re-generate

**เมื่อ QA พิมพ์ว่า:**
> "อัปเดตผล" หรือ "update status" หรือ "re-generate"

**Claude Code ต้องทำ:**
1. อ่าน TCM sheet ล่าสุด
2. ตรวจสอบว่ามี Status ที่ยังว่างอยู่หรือไม่ — ถ้ามีให้แจ้ง QA
3. Generate ไฟล์ใหม่ทับของเดิม หรือบันทึก version ใหม่ใน `output/`

---

### คำสั่งที่ 3: อัปเดต Template

**เมื่อ QA พิมพ์ว่า:**
> "อัปเดต template" หรือ "แก้ template" หรือ "เพิ่ม TS ใหม่"

**Claude Code ต้องทำ:**
1. ถามว่าต้องการแก้ไขอะไร:
   - เพิ่ม/ลด Test Scenario (TSID)
   - เพิ่ม/ลด Test Case ใน Scenario ที่มีอยู่
   - แก้ข้อมูล Sign-off persons
   - แก้ Layout/Format ของ Word
2. อัปเดตไฟล์ใน `templates/` พร้อมบันทึก version เก่าไว้ใน `archive/`
3. อัปเดต Section "Test Scenarios" ใน CLAUDE.md นี้ด้วย

---

### คำสั่งที่ 3b: Run One-Shot (แนะนำ)

**เมื่อ QA พิมพ์ว่า:**
> "run" หรือ "รัน" หรือ "generate ทีเดียว"

**Claude Code ต้องแนะนำให้รัน:**
```bash
python scripts/run.py
```

**run.py ทำงานอย่างไร:**
1. อ่านไฟล์ `.xlsx` ล่าสุดใน `input/`
2. เปรียบเทียบกับ snapshot ครั้งที่แล้ว (เก็บใน `.snapshot.json`)
3. แสดง diff ว่ามีอะไรเปลี่ยน (TC/status)
4. รัน `generate_report.py` ทันที
5. บันทึก snapshot ใหม่แล้วจบ (ไม่ loop)

**ตัวอย่าง output:**
```
[12:34:56] Input: input/BRS CPALL (DCPS)__TestCase.xlsx
[12:34:56] Changes since last run:
  TS_01: Pass 9→10  Not Start 1→0
  Total: Pass 38→39  Not Start 1→0

Regenerating...
✓ Saved: output/BRS_CPALL_DCPS_TestResult_20260325.docx
[12:34:58] Done.
```

---

### คำสั่งที่ 3d: Auto-Watch และ Re-generate อัตโนมัติ

**เมื่อ QA พิมพ์ว่า:**
> "watch" หรือ "auto-watch" หรือ "ดูการเปลี่ยนแปลงอัตโนมัติ"

**Claude Code ต้องแนะนำให้รัน:**
```bash
# Default 5s poll
python3 scripts/watch.py

# Custom interval (10s)
python3 scripts/watch.py 10
```

**watch.py ทำงานอย่างไร:**
1. ตรวจ `mtime` ของ `input/*.xlsx` ทุก 5 วินาที (configurable)
2. เมื่อ mtime เปลี่ยน → อ่าน TCM sheet เปรียบเทียบ snapshot ก่อนหน้า
3. แสดง diff (status count + TCID ที่เปลี่ยน) แล้วเรียก `generate_report.py` อัตโนมัติ
4. กด `Ctrl+C` เพื่อหยุด

**ตัวอย่าง output:**
```
[12:34:56] Watching input/BRS CPALL (DCPS)__TestCase.xlsx (poll: 5s)
[12:35:01] Change detected!
  TS_01: Pass 9→10  Not Start 1→0
  Total: Pass 38→39  Not Start 1→0
Regenerating...
Input  : input/BRS CPALL (DCPS)__TestCase.xlsx
...
✓ Saved: output/BRS_CPALL_DCPS_TestResult_20260325.docx
[12:35:03] Done.
[12:35:03] Watching input/BRS CPALL (DCPS)__TestCase.xlsx (poll: 5s)
```

**Edge cases ที่จัดการได้:**
- Excel เปิดอยู่ (`~$` lock file) → skip cycle, แสดง "Excel locked, waiting..."
- openpyxl อ่านไม่ได้ (mid-save) → retain last snapshot, แสดง warning
- generate_report.py fail → แสดง returncode error, ไม่ exit รอ cycle ถัดไป
- ไม่มีไฟล์ใน input/ → แสดง warning, รอ cycle ถัดไป

---

### คำสั่งที่ 4: สรุป Summary Report

**เมื่อ QA พิมพ์ว่า:**
> "สรุปผล" หรือ "summary" หรือ "ผลทดสอบเป็นยังไง"

**Claude Code ต้องตอบในรูปแบบ:**
```
📊 Test Result Summary — [ProjectName] [Sprint]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total TC:     39   ██████████  100%
Pass:         38   █████████▌   97%
Fail:          1   ▌             3%
In-Progress:   0
Block:         0
Cancel:        0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SIT Exit Criteria:
  ✅ Execution 100% complete
  ✅ Pass rate ≥ 90%  (97%)
  ✅ Critical defects = 0
```

---

### คำสั่งที่ 5: เพิ่ม Test Scenario ใหม่

**เมื่อ QA พิมพ์ว่า:**
> "เพิ่ม TS ใหม่" หรือ "add test scenario"

**Claude Code ต้องทำ:**
1. ถาม TSID ใหม่ (เช่น `TS_09`), ชื่อ Scenario, จำนวน TC
2. เพิ่ม rows ใน sheet TCM ของ Excel
3. เพิ่ม row ใน sheet SUMMARY (formula COUNTIFS จะคำนวณให้อัตโนมัติ)
4. เพิ่ม Section ใหม่ใน Word Template (ตาราง TC + placeholder Screenshot)
5. อัปเดตตาราง "Test Scenarios ที่รองรับ" ใน CLAUDE.md นี้

---

## 📏 กฎการสร้างไฟล์ Word

เมื่อ generate Word Claude Code ต้องปฏิบัติตามกฎต่อไปนี้:

### การจัดรูปแบบ
- Font: **Arial** ทุก element
- หน้ากระดาษ: A4 (ไม่ใช่ US Letter)
- Margin: 1 นิ้วทุกด้าน
- **Header:** Logo image (`word/media/image1.png`) — มาจาก template โดยตรง (ไม่ต้อง inject)
- **Footer:** Copyright + Page Number — มาจาก template โดยตรง (ไม่ต้อง inject)

### สีที่ใช้ใน Table
| สถานะ | Background Color | Hex |
|---|---|---|
| Pass | เขียวอ่อน | `#E2EFDA` |
| Fail | ส้มอ่อน | `#FCE4D6` |
| In-progress | เหลืองอ่อน | `#FFF2CC` |
| Block | ชมพูอ่อน | `#F4B8C1` |
| Cancel | เทาอ่อน | `#EDEDED` |
| Not Start | ฟ้าอ่อน | `#DAEEF3` |
| Header | น้ำเงิน | `#2E75B6` |
| Title/Dark | น้ำเงินเข้ม | `#1F3864` |

### โครงสร้างตาราง Test Result (Section 5)
แต่ละ TS มี 2 ส่วน:
1. **ตาราง TC** — คอลัมน์: TCID | Test Case Description | Expected Result | P/N | Status | Executed Date
2. **Evidence block** — placeholder สำหรับแนบ Screenshot (เป็น italic gray text)

---

## ⚠️ กฎที่ต้องปฏิบัติเสมอ

1. **อ่าน CLAUDE.md ก่อนทำทุกครั้ง** — ห้าม assume โครงสร้างจาก memory
2. **อย่าแก้ไข `templates/` โดยตรง** — ให้ copy ไป `input/` ก่อน เว้นแต่ได้รับคำสั่ง "อัปเดต template" ชัดเจน
3. **Backup ก่อนเขียนทับ** — ถ้าไฟล์ output มีอยู่แล้ว ให้ copy ไป `archive/` ก่อน
4. **ตรวจสอบ Status ว่างก่อน generate** — ถ้ามี TC ที่ Status ยังว่างอยู่ ให้แจ้ง QA ว่ามีกี่ TC และ TCID อะไรบ้าง แล้วถามว่าต้องการ generate ต่อไหม
5. **ชื่อไฟล์ใช้ underscore** — ห้ามมี space ในชื่อไฟล์ output
6. **วันที่ใช้ format `DD MMM YYYY`** — เช่น `23 Mar 2026` ไม่ใช่ `23/03/2026`
7. **ภาษาไทยใน Expected Result** — เก็บภาษาไทยไว้ตามต้นฉบับ ไม่ต้องแปล

---

## 🔄 Workflow มาตรฐาน (ทุก Sprint)

```
Sprint เริ่มต้น
      │
      ▼
1. QA copy templates/Test_Case_Template.xlsx → input/[Project]_TestCase.xlsx
      │
      ▼
2. QA กรอก PROJECT_INFO sheet (Project Code, Customer, Sprint, etc.)
      │
      ▼
3. QA กรอก TCM sheet (เพิ่ม TC ถ้ามีใหม่, กรอก Status หลังรัน test)
      │
      ▼
4. พิมพ์ "generate report" → Claude Code สร้างไฟล์ Word ใน output/
      │
      ▼
5. QA แนบ Screenshot ลงใน Word (manual ใน Word)
      │
      ▼
6. QA ส่ง Sign-off Document ให้ลูกค้า
      │
      ▼
Sprint ถัดไป → ทำซ้ำตั้งแต่ข้อ 1
```

---

## 🛠️ Dependencies

```bash
# Python (สำหรับ generate_report.py — วิธีหลัก)
pip install python-docx openpyxl pandas lxml

# Node.js (สำหรับ build_template.cjs — generate จาก scratch)
npm install docx          # ติดตั้งใน D:/Automate/qa_automate/
```

### วิธี Generate (3 แบบ)

| วิธี | Script | ข้อดี | ข้อเสีย |
|---|---|---|---|
| **One-shot (แนะนำ)** | `scripts/run.py` | รันครั้งเดียว, แสดง diff, บันทึก snapshot | ต้องพิมพ์คำสั่งเอง |
| Python | `scripts/generate_report.py` | ใช้ template จริง, header/footer/image ถูกต้อง | ไม่แสดง diff |
| Node.js | `scripts/build_template.cjs` | ไม่ต้องพึ่ง template | header เป็น text fallback (ไม่มีรูป) |

```bash
# One-shot — วิธีแนะนำ
python scripts/run.py

# Python — generate ตรงๆ
python3 scripts/generate_report.py

# Node.js
node scripts/build_template.cjs
# จากนั้น fix duplicate styles ด้วย:
python3 -c "
import zipfile, shutil, os
from lxml import etree
# ... (ดู scripts/build_template.cjs สำหรับ full fix script)
"
```

> **หมายเหตุ Node.js:** `docx` npm v9.x สร้าง `styles.xml` ที่มี `Heading1`/`Heading2` ซ้ำ
> ต้อง dedup หลัง generate ทุกครั้ง — Python script ไม่มีปัญหานี้

---

## 📝 Change Log

| วันที่ | เปลี่ยนแปลง | โดย |
|---|---|---|
| 24 Mar 2026 | สร้าง CLAUDE.md เริ่มต้น + Template v1.0 | Demo User |
| 24 Mar 2026 | เพิ่ม Header (logo image) + Footer (copyright/page) ใน Template v1.1 | Demo User |
| 24 Mar 2026 | เพิ่ม Table of Contents (SDT/TOC) ใน Template v1.2 | Demo User |
| 24 Mar 2026 | เพิ่ม Evidence placeholder paragraphs พร้อม TCID ใน Template v1.3 | Demo User |
| 24 Mar 2026 | เพิ่ม PieChart + BarChart ใน Excel SUMMARY sheet (Template v1.4) | Demo User |
| 24 Mar 2026 | เพิ่ม Status "Not Start" (สีฟ้าอ่อน #DAEEF3) ใน Template v1.5 + script | Demo User |
| 24 Mar 2026 | Script auto-generate TCID list ใต้ evidence header ทุก TS section | Claude |
| 24 Mar 2026 | เพิ่ม `scripts/build_template.cjs` (Node.js alternative generator) | Claude |
| 25 Mar 2026 | เพิ่ม `scripts/watch.py` — polling daemon ตรวจ input/*.xlsx re-generate อัตโนมัติพร้อม diff | Claude |
| 25 Mar 2026 | เพิ่ม `scripts/run.py` — one-shot command แทน watch, diff vs .snapshot.json แล้วจบ | Claude |
| 25 Mar 2026 | แก้ `generate_report.py` — เปลี่ยน path จาก `template/` เป็น `templates/` | User |

> **วิธีอัปเดต Change Log:** เมื่อมีการแก้ไข Template หรือเพิ่ม Scenario ใหม่
> ให้บันทึกในตารางนี้ พร้อมวันที่และชื่อผู้แก้ไขทุกครั้ง
