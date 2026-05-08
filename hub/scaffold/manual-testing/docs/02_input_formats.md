# App Architecture Document
# สำหรับใช้กับ Claude Code + Playwright Testing

> **วัตถุประสงค์**: เอกสารนี้ช่วยให้ Claude เข้าใจโครงสร้าง app ก่อนเขียน test
> อัปเดตเมื่อมีการเปลี่ยนแปลง flow หรือ feature หลัก

---

## 1. App Overview

**ชื่อ app**: MyShop — ระบบ E-Commerce สำหรับธุรกิจ SME  
**เป้าหมาย**: ให้ร้านค้าสามารถขายสินค้าออนไลน์ และจัดการ order ได้ครบวงจร  
**Tech Stack**:

| Layer       | Technology                          |
|-------------|--------------------------------------|
| Frontend    | Next.js 14 (App Router), TypeScript  |
| Styling     | Tailwind CSS + shadcn/ui             |
| Auth        | NextAuth.js v5                       |
| Backend     | Next.js Route Handlers (API Routes)  |
| Database    | PostgreSQL + Prisma ORM              |
| Payment     | Stripe (sandbox + production)        |
| File Upload | AWS S3                               |
| Email       | Resend (transactional email)         |
| Hosting     | Vercel (frontend) + Railway (DB)     |

---

## 2. URL Structure (Route Map)

```
/ ─────────────────────────────── Landing page (public)
│
├── /login ───────────────────── Login page (redirect ถ้า logged in)
├── /register ────────────────── Register page
├── /forgot-password ─────────── ขอ reset password
├── /reset-password?token=... ── ตั้ง password ใหม่
│
├── /products ────────────────── Product listing (public)
│   └── /products/[slug] ─────── Product detail (public)
│
├── /search?q=... ────────────── Search results (public)
│
├── /cart ────────────────────── Cart (guest + user, ใช้ localStorage สำหรับ guest)
│
├── /checkout ────────────────── Checkout (requires login)
│   └── /checkout/success ─────── Order confirmed page
│
├── /account ─────────────────── User account hub (requires login)
│   ├── /account/orders ────────── Order history
│   ├── /account/orders/[id] ───── Order detail
│   ├── /account/profile ────────── แก้ไข profile
│   └── /account/addresses ──────── จัดการที่อยู่
│
└── /admin ───────────────────── Admin dashboard (requires admin role)
    ├── /admin/products ─────────── จัดการสินค้า
    │   ├── /admin/products/new ─── เพิ่มสินค้าใหม่
    │   └── /admin/products/[id] ── แก้ไขสินค้า
    ├── /admin/orders ───────────── จัดการ orders ทั้งหมด
    │   └── /admin/orders/[id] ──── Order detail + update status
    ├── /admin/customers ────────── ดู customer list
    └── /admin/settings ─────────── ตั้งค่าร้านค้า
```

---

## 3. User Roles & Access Control

| Role    | สร้างอย่างไร              | เข้าถึงได้                            |
|---------|--------------------------|---------------------------------------|
| `guest` | ไม่ต้อง login            | public pages, cart (localStorage)     |
| `user`  | register หรือ Google SSO | + /checkout, /account/*               |
| `admin` | สร้างโดย superadmin      | + /admin/*, ดู order ทุกคน            |

**Redirect rules:**
- `/checkout` → redirect `/login?callbackUrl=/checkout` ถ้าเป็น guest
- `/admin/*` → redirect `/login` ถ้าไม่ใช่ admin (403 page ถ้าเป็น user)
- `/login`, `/register` → redirect `/` ถ้า logged in แล้ว

---

## 4. Core User Flows

### Flow A: Guest → Purchase (Happy Path)

```
1. เข้า /products
2. คลิก product card → /products/[slug]
3. เลือก variant (size/color ถ้ามี) → "Add to Cart"
4. cart badge แสดง count
5. คลิก cart icon → /cart
6. ตรวจสอบ items → "Proceed to Checkout"
7. Redirect /login?callbackUrl=/checkout
8. Login สำเร็จ → redirect /checkout
9. กรอก shipping address
10. เลือก shipping method
11. กรอก card (Stripe Elements)
12. "Place Order" → loading state
13. Redirect /checkout/success?orderId=xxx
14. รับ email confirmation (Resend)
```

### Flow B: Registered User → Purchase (Short Path)

```
1. Login → /
2. /products → เลือกสินค้า → Add to Cart
3. /cart → "Proceed to Checkout"
4. Address ถูก pre-fill จาก saved addresses
5. กรอก card → "Place Order"
6. /checkout/success
```

### Flow C: Admin — จัดการ Product

```
1. /admin/products → เห็น product list (table)
2. "Add Product" → /admin/products/new
3. กรอก: ชื่อ, description, price, stock, images (upload)
4. เลือก category, tags
5. "Publish" หรือ "Save as Draft"
6. redirect /admin/products → product ปรากฏใน list

Edit:
3b. คลิก product row → /admin/products/[id]
3c. แก้ไขฟอร์ม → "Update"
3d. Toast "Product updated"

Delete:
3e. คลิก "Delete" → confirm modal
3f. "Confirm Delete" → product ถูกลบ → ปรากฏใน list ทันที (optimistic update)
```

### Flow D: Admin — จัดการ Order Status

```
1. /admin/orders → เห็น order list (status filter: all/pending/processing/shipped/delivered/cancelled)
2. คลิก order row → /admin/orders/[id]
3. ดู order detail + customer info
4. Dropdown "Update Status" → เลือก status ใหม่
5. "Save" → email ถูกส่งให้ customer อัตโนมัติ
```

---

## 5. Key UI Components & Behaviors

### Cart
- **Guest cart**: เก็บใน `localStorage` key `cart_items`
- **User cart**: sync กับ database เมื่อ login
- **Merge**: เมื่อ guest login, localStorage cart ถูก merge กับ db cart
- **Badge**: real-time update ผ่าน React state (ไม่ต้อง reload)
- **Stock check**: ถ้า item หมด stock ตอน checkout → error inline

### Product Variants
- สินค้าบางชิ้นมี variant (เช่น เสื้อมี size S/M/L/XL, color ดำ/ขาว)
- ต้องเลือก variant ก่อน "Add to Cart" จึงจะ enable ได้
- ถ้า variant out of stock → ปุ่ม disabled + แสดง "Out of Stock"

### Forms (ทั้ง app ใช้ React Hook Form + Zod)
- Validation เกิดขึ้น onBlur และ onSubmit
- Error message แสดงใต้ field นั้นๆ (ไม่ใช่ toast)
- Submit button disabled ระหว่าง loading

### Modals & Dialogs
- ใช้ Radix UI Dialog component
- ทุก destructive action (delete, cancel order) ต้องผ่าน confirm modal
- Modal มี animation 200ms (fade + scale)
- กด Escape หรือคลิก overlay → ปิด modal

### Toast Notifications
- ใช้ sonner library
- Success: สีเขียว, ปรากฏ 3 วินาที, bottom-right
- Error: สีแดง, ปรากฏ 5 วินาที
- ไม่ block interaction

### Loading States
- Page transition: loading.tsx skeleton
- Button loading: spinner แทนที่ text + disabled
- Table loading: skeleton rows 5 แถว

---

## 6. API Endpoints (สำหรับ API-level testing)

### Auth
```
POST /api/auth/signin          ← NextAuth endpoint
POST /api/auth/signout
GET  /api/auth/session
```

### Products
```
GET    /api/products           ← list (query: page, limit, category, q)
GET    /api/products/[id]      ← detail
POST   /api/products           ← create (admin only)
PATCH  /api/products/[id]      ← update (admin only)
DELETE /api/products/[id]      ← delete (admin only)
```

### Cart
```
GET    /api/cart               ← get current cart
POST   /api/cart/items         ← add item
PATCH  /api/cart/items/[id]    ← update quantity
DELETE /api/cart/items/[id]    ← remove item
DELETE /api/cart               ← clear cart
```

### Orders
```
POST   /api/orders             ← create order + Stripe payment intent
GET    /api/orders             ← list (user: own orders, admin: all)
GET    /api/orders/[id]        ← detail
PATCH  /api/orders/[id]/status ← update status (admin only)
```

---

## 7. State Management

```
Global state (Zustand):
├── authStore       → session, user info
├── cartStore       → cart items, total, count
└── uiStore         → modal state, toast queue

Server state (React Query / fetch):
├── products        → cached, stale 5 min
├── orders          → no cache (real-time)
└── admin data      → no cache
```

---

## 8. Error States ที่ต้อง Test

| Scenario                              | Expected Behavior                                |
|---------------------------------------|--------------------------------------------------|
| Login ด้วย credentials ผิด            | Error "Invalid email or password" ใต้ form       |
| Register ด้วย email ที่มีอยู่แล้ว     | Error "Email already in use"                     |
| Add to cart สินค้า out of stock       | Error toast "This item is out of stock"          |
| Checkout ด้วย card ถูก decline        | Error "Your card was declined" ใน Stripe element |
| เข้า /admin ด้วย user role            | Redirect /403 หรือ /login                        |
| Session หมดอายุระหว่าง checkout       | Modal "Session expired" + redirect /login        |
| Upload รูปขนาดเกิน 5MB                | Error "File size must be less than 5MB"          |
| Network timeout                       | Toast "Something went wrong. Please try again."  |

---

## 9. Test Data & Seeding

### Test Accounts (`.env.test`)
```
TEST_USER_EMAIL=testuser@myshop.test
TEST_USER_PASSWORD=TestUser123!

TEST_ADMIN_EMAIL=testadmin@myshop.test
TEST_ADMIN_PASSWORD=TestAdmin123!
```

### Seed Data (อยู่ใน DB ของ test environment เสมอ)
| Type      | Detail                                        |
|-----------|-----------------------------------------------|
| Products  | 20 products, IDs 1–20 (IDs ไม่เปลี่ยน)        |
| Categories| Electronics, Clothing, Books, Home (4 รายการ) |
| Variants  | Product ID 5, 10, 15 มี size+color variants   |
| Stock     | Product ID 20 เป็น "out of stock" เสมอ         |

### Stripe Test Cards
```
สำเร็จ:        4242 4242 4242 4242  exp: 12/34  cvv: 123
ถูก Decline:   4000 0000 0000 0002  exp: 12/34  cvv: 123
Require 3DS:   4000 0027 6000 3184  exp: 12/34  cvv: 123
```

---

## 10. ข้อมูลเพิ่มเติมสำหรับ Claude

### สิ่งที่เปลี่ยนบ่อย (ระวังเป็นพิเศษ)
- Product slug อาจเปลี่ยนเมื่อแก้ชื่อสินค้า → ใช้ ID แทน slug ใน test
- Order ID เป็น UUID ไม่สามารถ hardcode ได้ → ดึงจาก response หรือ URL

### สิ่งที่ไม่ควร Test ผ่าน Playwright
- Email delivery (ใช้ unit test + Resend webhook test แทน)
- Stripe webhook processing (ใช้ Stripe CLI + integration test)
- Performance / load testing (ใช้ k6 แทน)

### Third-party ที่ต้อง Mock ใน Test
```typescript
// Stripe Elements → ไม่สามารถ interact ได้ตรงๆ ใน test
// ใช้ Stripe test card + iframe interaction
await page.frameLocator('[title="Secure card number input frame"]')
         .getByPlaceholder('Card number')
         .fill('4242 4242 4242 4242');

// Google OAuth → disable ใน test environment
// ใช้ NEXTAUTH_TEST_MODE=true เพื่อ bypass OAuth
```
