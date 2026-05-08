# ตัวอย่าง Requirement Document (Ideal Format)
# BA Agent จะวิเคราะห์ไฟล์นี้และสร้าง test cases ได้โดยไม่ต้องถามเพิ่ม

---

## Feature: User Login

### Meta
- Feature ID: F-001
- Module: Authentication
- Priority: Must Have
- Actors: Guest, User, Admin

### Description
ผู้ใช้ที่ลงทะเบียนแล้วสามารถ login ด้วย email + password
เพื่อเข้าถึง features ที่ต้องการ authentication

### Preconditions
- มี account ในระบบแล้ว (email verified)
- ยังไม่ได้ login
- อยู่ที่ /login

### Happy Path
1. กรอก email ที่ถูกต้อง
2. กรอก password ที่ถูกต้อง
3. คลิก "Sign in"
4. User → redirect /dashboard, แสดง "Welcome, [ชื่อ]" ที่ header
5. Admin → redirect /admin/dashboard

### Error Conditions
| Condition                    | Expected Message                              |
|------------------------------|-----------------------------------------------|
| email format ผิด             | "Please enter a valid email address"          |
| password ว่าง                | "Password is required"                        |
| credentials ผิด              | "Invalid email or password"                   |
| login ผิด 5 ครั้ง             | "Account locked. Try again in 15 minutes."   |
| account ไม่ verify email     | "Please verify your email before signing in"  |

### Business Rules
- lock account หลังผิด 5 ครั้งภายใน 15 นาที (นับ per account ไม่ใช่ per IP)
- หลัง lock ต้องรอครบ 15 นาที ถึงจะ unlock อัตโนมัติ
- session หมดอายุใน 24 ชั่วโมง
- ถ้า user ที่ login แล้วเข้า /login → redirect /dashboard

### Permissions
| Action          | Guest | User | Admin |
|-----------------|-------|------|-------|
| เข้า /login     | ✓     | redirect /dashboard | redirect /admin |
| submit form     | ✓     | —    | —     |
| logout          | —     | ✓    | ✓     |

### Selectors
| Element           | data-testid          |
|-------------------|----------------------|
| Email input       | email-input          |
| Password input    | password-input       |
| Sign in button    | signin-button        |
| Error message     | auth-error           |
| Forgot password   | forgot-password-link |

### Out of Scope
- Google OAuth (test แยกใน feature F-015)
- "Remember me" checkbox (phase 2)
- 2FA / OTP (phase 3)
