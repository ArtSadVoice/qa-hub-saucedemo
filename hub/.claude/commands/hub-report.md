สร้าง Cross-Project Summary Report จาก Hub API ครอบทุก project

## วิธีใช้

```
/hub-report               # report ทุก project
/hub-report --active      # เฉพาะ active projects
/hub-report --attention   # เฉพาะ project ที่มีปัญหา (gate ไม่ผ่าน / bug open)
```

## ขั้นตอน

**1. parse $ARGUMENTS:**
- `--active` = กรองเฉพาะ phase=active
- `--attention` = กรองเฉพาะ project ที่ release gate ไม่ผ่านหรือมี Critical/High bug

**2. ใช้ Hub Report Agent:**
อ่าน `.claude/agents/hub-report.md` → ทำตาม protocol ทีละขั้นตอน

**3. บันทึก report:**
`hub_report_YYYYMMDD_HHMMSS.md` ใน working directory ของ Hub

**4. แสดง summary table** ในหน้า terminal ทันที ก่อนบอก path ของ full report
