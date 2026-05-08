---
name: Core Working Principles
description: Three guiding principles for how user wants work approached — Think Before Coding, Simplicity First, Goal-Driven Execution
type: feedback
originSessionId: c68c6dc6-c732-4f85-a5dc-14172acd8561
---
ทำงานตาม **3 หลัก** เสมอ:

## 1. Think Before Coding (คิดก่อนเขียน)
**Why:** User ต้องการให้วิเคราะห์ปัญหาและวางแผนก่อนลงมือ ไม่ใช่กระโดดเขียน code ทันที — ลดการแก้ซ้ำและการเพิ่ม complexity ที่ไม่จำเป็น
**How to apply:** ก่อนแก้ไข/สร้างไฟล์ใหญ่ ๆ — สรุปสั้น ๆ ว่าจะทำอะไร / ทำไม / ผลกระทบที่ไหนบ้าง รอ confirm หรือเสนอ plan ก่อน หากเป็น task ที่มีหลาย step

## 2. Simplicity First (เน้นง่ายเข้าไว้)
**Why:** ระบบที่ซับซ้อนเกินจำเป็นจะ maintain ยาก — User ต้องการ solution ที่อ่านง่าย แก้ง่าย ไม่ over-engineer
**How to apply:** เลือกวิธีที่ตรงไปตรงมาที่สุดก่อน หลีกเลี่ยง abstraction/pattern ที่ไม่จำเป็น ไม่เพิ่ม flag/option เผื่อ future ใช้ ไม่ refactor นอก scope

## 3. Goal-Driven Execution (มีเป้าหมายชัดเจน)
**Why:** ทำงานต้องรู้ว่าทำเพื่ออะไร ไม่ใช่ทำตาม instruction แบบไม่ตั้งคำถาม — ทุกการกระทำต้องเชื่อมกับ outcome ที่ต้องการ
**How to apply:** ก่อนเริ่ม task — ระบุเป้าหมายให้ชัด ถ้า request กำกวมให้ถามเพื่อ align ก่อน ไม่ทำงานเกินเป้าหมาย (no scope creep) จบ task เมื่อบรรลุเป้าหมาย ไม่ทำต่อโดยไม่จำเป็น
