# คู่มือการเขียน CLAUDE.md สำหรับโปรเจกต์ใหม่

## CLAUDE.md คืออะไร

ไฟล์ที่บอก Claude Code ว่า project นี้คืออะไร โครงสร้างไฟล์เป็นอย่างไร
และต้องทำอะไรเมื่อได้รับคำสั่ง — Claude จะอ่านไฟล์นี้ก่อนทำงานทุกครั้ง

## ส่วนที่ต้องมีเสมอ (Must Have)

1. **Project Overview** — ชื่อ app, stack, base URL
2. **Project Structure** — โครงสร้าง directory
3. **User Roles** — role ทั้งหมดและสิ่งที่แต่ละ role ทำได้
4. **URL Structure** — URL ของทุกหน้า
5. **Selector Strategy** — ลำดับความสำคัญของ selector
6. **Test Scenarios** — ตาราง TS_01..TS_XX
7. **Rules** — กฎที่ Claude ต้องปฏิบัติ

## ตัวอย่างที่ดี vs ไม่ดี

### URL Structure
```
❌ ไม่ดี:
"มีหน้า login และ dashboard"

✅ ดี:
/login          ← Login page (redirect ถ้า logged in แล้ว)
/dashboard      ← ต้อง login, user role
/admin          ← ต้อง login, admin role เท่านั้น
/admin/[resource] → 403 ถ้าเป็น user role
```

### Selector Strategy
```
❌ ไม่ดี:
"ใช้ selector ที่เหมาะสม"

✅ ดี:
1. getByRole('button', { name: 'Submit' })
2. getByTestId('submit-button')
3. getByLabel('Email address')
ห้ามใช้: .btn-primary, //button[@type="submit"]
```

## วิธีใช้ Template

1. เปิด `templates/CLAUDE.md.template`
2. แทนที่ `[PROJECT_NAME]`, `[BASE_URL]`, `[STACK]`
3. กรอก User Roles และ URL Structure ของ app จริง
4. เพิ่ม data-testid table ถ้ามี
5. บันทึกเป็น `CLAUDE.md` ที่ root ของ project
