# Mobile Audit — QA Hub Demo Dashboard

**Initial audit**: 2026-05-06 (375 × 667)
**All 5 phases shipped**: 2026-05-06 — see PRs #28 / #29 / #30 / #31 (#32 = Phase 5 verify)
**Method**: Playwright headed browser → BasicAuth → walk every section + capture screenshots + DOM/style introspection

Screenshots in this folder: `01-..-11-*.png` (BEFORE) and `AFTER/`, `AFTER-PHASE2/`, `AFTER-PHASE3/`, `AFTER-PHASE4/`, `AFTER-PHASE5/`.

---

## ✅ Status — All phases complete

| Phase | PR | Highlights | Verified at |
|---|---|---|---|
| 1 — Unblock | [#28](https://github.com/ArtSadVoice/qa-hub-saucedemo/pull/28) | sidebar 0→260, overlay logic, padding trim, table scroll | 375 / 1440 |
| 2 — Form & Topbar | [#29](https://github.com/ArtSadVoice/qa-hub-saucedemo/pull/29) | schedule form stack, quick actions 2×2, tap targets | 375 / 414 / 1440 |
| 3 — Tables → Cards | [#30](https://github.com/ArtSadVoice/qa-hub-saucedemo/pull/30) | Scenario Summary / Run History / Schedule become stacked cards on ≤640 | 375 / 1440 |
| 4 — Polish | [#31](https://github.com/ArtSadVoice/qa-hub-saucedemo/pull/31) | 44px taps, About form stack, modal padding, Stage 5 dropdown fix, TEMPLATES_AUTO_RELOAD | 375 / 1440 |
| 5 — Verify | this PR | regression at 320 / 414, code-block wrap fix, REPORT update | 320 / 375 / 414 / 1440 |

### Final viewport sweep

| Viewport | Body width | Status |
|---|---|---|
| 320 × 568 (iPhone SE 1st gen) | 305 / 317 | ✅ no overflow; pipeline `.tl-output code` wraps via `overflow-wrap:anywhere` |
| 375 × 667 (iPhone SE 2nd/3rd gen) | 360 | ✅ no overflow |
| 414 × 896 (iPhone Pro Max) | 399 | ✅ no overflow |
| 1440 × 900 (desktop) | 1440 | ✅ no regression — sidebar 230, topbar full, tables full-width |

### Key metrics: BEFORE → AFTER (375 × 667)

| Metric | Before | After |
|---|---|---|
| `body.scrollWidth` | 533 (overflow) | 360 ✓ |
| Sidebar width | 0 (broken) | 260 ✓ |
| Overlay state (closed) | always block | none ✓ |
| Stats grid | 3 cols cramped | 2 cols at ≤480 ✓ |
| Wide tables | overflow page | stacked cards ✓ |
| Tap target (.btn) | ~36px | 44px ✓ |
| Schedule form min-width | 640+ | viewport-fit ✓ |

---

## Original audit (kept for reference)

---

## TL;DR

ทุกหน้า render ที่ความกว้างประมาณ **533px** บน viewport 375px → **horizontal scroll ทั้ง app**. รากของปัญหาอยู่ที่ 4 จุด:

1. `--sidebar:0px` ที่ `@media(max-width:640px)` ทำให้ sidebar **width 0** — hamburger menu คลิกได้แต่ไม่มีอะไรโผล่
2. `#sb-overlay{display:block !important}` ใน media query **ไม่ผูกกับ state ของ sidebar** → overlay ดำคลุมหน้าจอตลอดเวลาบน mobile
3. Topbar / content padding ยังเป็น 24px ทั้งสองข้าง + buttons เยอะเกินไป → topbar ดันความกว้างเกิน viewport
4. Tables (Scenario Summary, Run History, Schedule) + Schedule form ไม่มี mobile pattern (responsive table / stacked form) → overflow แน่นอน

แก้ 4 จุดนี้ก่อนจะปลดล็อค ~80% ของปัญหาที่เหลือ

---

## Issues

### P0 — Blockers (mobile ใช้งานไม่ได้)

| # | Issue | Where | Evidence |
|---|---|---|---|
| P0-1 | Sidebar width 0px → ไม่มี nav บน mobile | `static/app.css:238` (`:root{--sidebar:0px}`) + `:58` (`.sidebar{width:var(--sidebar)}`) | screenshot `09-sidebar-open.png` — กดปุ่ม ☰ แล้วไม่มีอะไรปรากฏ; computed `width: 0px` |
| P0-2 | Overlay ดำคลุมตลอดบน mobile (sidebar ปิด) | `static/app.css:243` (`#sb-overlay{display:block !important}`) | screenshot `01-dashboard-top.png` — เนื้อหาทั้งหน้าโดน dim 30% |
| P0-3 | Body overflow แนวนอน 533px (viewport 375) | `.main`, `.topbar`, `.content` ทั้งหมด width ≈533 | DOM measure: `bodyScrollWidth=533, clientWidth=360` |

### P1 — Severe (ใช้ได้แต่ลำบาก)

| # | Issue | Where | Notes |
|---|---|---|---|
| P1-1 | Topbar buttons 5 ตัว (⌘K, 🔔, 🔄, 🌙) + h1 + project pill (max-width:220px) + Ready badge | `dashboard.html:101-112` | ที่ 375px เบียดจน h1 ตัด, pill ซ้อน buttons |
| P1-2 | `.topbar{padding:13px 24px}` + `.content{padding:20px 24px}` | `static/app.css:82, 89` | ที่ 375 viewport — 48px เป็น padding ล้วน เหลือ content จริง 327px |
| P1-3 | Stats grid `auto-fit, minmax(130px, 1fr)` → fit 3 cols ที่ 414px | `static/app.css:99` | บน 375 ทำให้ overflow; ควร force 2 cols ที่ ≤480 |
| P1-4 | Test Scenario Summary table: 7 cols (TSID, Description, Total, Pass, Fail, In-Prog, Block) | `dashboard.html:217-225` | ไม่มี wrapper `overflow-x:auto` หรือ mobile card layout |
| P1-5 | Run History table — เหมือนกัน | `dashboard.html` (search "Run History" table) | overflow แน่นอน |
| P1-6 | Schedule form: 4 columns side-by-side (`Project / Action / Tag / Environment`) | `dashboard.html` schedule section + `.form-field{min-width:160px}` (`app.css:199`) | 160×4 = 640 minimum |
| P1-7 | Quick action bar: 4 ปุ่ม `min-width:130px` | `dashboard.html:171-176` | บน 375 จะเด้งเป็น 2×2 (ดี) แต่ pixels ก็ยังตึง |

### P2 — Moderate (annoying)

| # | Issue | Where | Notes |
|---|---|---|---|
| P2-1 | Trend SVG `min-width:300px` ใน scrollable wrapper | `static/app.css:296-297` | ok-ish (มี overflow-x:auto) แต่ทำให้ scroll สอง wheels |
| P2-2 | Pipeline stage cards: long text wrap แย่ | `dashboard.html` stages | เพราะ font-size 13px + padding 18px 20px = ตึง |
| P2-3 | Bug Reports filter row: dropdown × 2 + "Log Bug" + "Export Excel" | `dashboard.html` bugs section | wrap ลง 2 แถว ok แต่ปุ่ม "Log Bug" สีแดงเด่นเกินไปบน mobile |
| P2-4 | Notif panel `width:320px;right:12px` | `dashboard.html:115` | ที่ 375 viewport ok แต่ ≤340 จะหลุด |
| P2-5 | Modals ใช้ `width:360px;max-width:90vw` หลายตัว | `static/app.css:235, 317` + inline | ok แต่ form field ข้างในยังเดิม |
| P2-6 | Form fields `min-width:160px` ทำให้ทั้งฟอร์มขั้นต่ำ ~340px ก็ยังเสี่ยง overflow ที่ 320 viewport | `static/app.css:199` | ควรเป็น 100% ที่ ≤480 |
| P2-7 | Code hints `min-width:180px` ใน Guide tab | `dashboard.html:1059-1075` | บางจุดใช้ที่ desktop layout — ตรวจ wrap |

### P3 — Minor / Polish

| # | Issue | Where |
|---|---|---|
| P3-1 | Tap targets บางตัวเล็กกว่า 44×44 (icon buttons topbar) | topbar buttons ราว 36-40px |
| P3-2 | Project info table: 2 cols labels/values — บน mobile ควร stack | `dashboard.html:200-205` |
| P3-3 | About section: branding form 2 cols → cram | `audit/mobile/10-about.png` |
| P3-4 | Schedule notify column wide enough? — ตรวจหลังแก้ form |
| P3-5 | Lightbox `max-width:92vw` ok แต่ caption ยังไม่มี mobile size |

---

## Plan — Phased

### Phase 1 — Unblock (target: 1-2 ชม.)
แก้ P0 ทั้งหมด → mobile ใช้งานได้ (nav + ไม่มี overlay ค้าง + ไม่มี horizontal scroll หลัก)

1. **Fix sidebar width**
   - `app.css:238` → ตั้ง `--sidebar:260px` (ไม่ใช่ 0) แต่ให้ `.main{margin-left:0}` เหมือนเดิม
   - sidebar ก็จะ slide-in ที่ 260px ตามเดิม
2. **Fix overlay logic**
   - ลบ `#sb-overlay{display:block !important}` ใน media query
   - ใส่ JS: `toggleSidebar()` toggle class `sb-show` บน overlay (open) / remove (close)
   - หรือ pure CSS: `.sidebar.sb-open ~ #sb-overlay{display:block}` (sibling selector)
3. **Reduce topbar/content padding ที่ ≤640**
   - `@media(max-width:640px){.topbar{padding:10px 12px}.content{padding:14px 12px}.card{padding:14px 14px}}`
4. **Stats grid: force 2 cols ที่ ≤480**
   - `@media(max-width:480px){.stats{grid-template-columns:repeat(2,1fr)}}`
5. **Table wrappers: add `overflow-x:auto`**
   - Wrap `#ts-table`, run history table, schedule table ด้วย `<div class="table-scroll">` + `.table-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}` (หรือเพิ่ม class ใน parent .card)

### Phase 2 — Form & Topbar (target: 1-2 ชม.)
แก้ P1-1, P1-6 ที่ยังเหลือหลัง Phase 1

6. **Topbar collapse**
   - ที่ ≤640: ซ่อน "Ready" badge, project pill (ย้ายไป sidebar/dropdown)
   - กลุ่ม icon buttons (🔔 + 🔄 + 🌙) ใส่ใน "more menu" (ปุ่มเดียว ⋮)
7. **Schedule form: stack ที่ ≤640**
   - เพิ่ม `@media(max-width:640px){.form-row{flex-direction:column}.form-field{min-width:100%}}`
8. **Quick action bar: 2×2 grid ชัดเจน**
   - เปลี่ยนจาก flex-wrap → grid 2 cols ที่ ≤480

### Phase 3 — Tables → Cards (target: 2-4 ชม.)
แก้ P1-4, P1-5 ให้สวยจริง (Phase 1 แค่ scroll ได้)

9. **Mobile card pattern สำหรับ Test Scenario Summary**
   - ที่ ≤640: hide `<thead>`, render แต่ละ row เป็น stacked card (ใช้ `[data-label]` + CSS `::before`)
10. **Mobile card pattern สำหรับ Run History**
    - same approach
11. **Schedule list**
    - same approach

### Phase 4 — Polish (target: 1 ชม.)
P2 + P3 — touch targets, modal padding, project info stack

12. Increase tap targets: `.btn-sm{min-height:36px}` → `min-height:44px` ที่ mobile
13. Modal `padding:20px` ที่ ≤640 (จาก 28px)
14. Branding form ใน About → 1 col ที่ mobile

### Phase 5 — Verify (target: 30 นาที)
15. Re-run Playwright audit ที่ 375×667, 414×896, 320×568
16. Compare before/after screenshots → ใส่ใน `audit/mobile/AFTER/`
17. ตรวจ regression ที่ desktop (1920×1080) — sidebar กลับมาที่ 230 (จากการแก้ #1 ต้องทดสอบให้แน่ใจว่า desktop ไม่หลุด)

---

## ไฟล์ที่จะแตะ

| File | Phase | Lines (โดยประมาณ) |
|---|---|---|
| `static/app.css` | 1, 2, 3, 4 | +60 -5 |
| `static/app.js` | 1 (overlay toggle) | +10 |
| `templates/dashboard.html` | 1 (table wrappers), 2 (topbar collapse) | +20 -2 |
| `audit/mobile/AFTER/*.png` | 5 | (new screenshots) |

ไม่ต้องแก้ `app.py`, ไม่ต้องแก้ schemas, validators, agents — งาน UI ล้วน

---

## Risks

- **Desktop regression**: การเปลี่ยน `--sidebar` value ใน media query อาจ leak — แก้ทดลองที่ 1024+ viewport
- **Sidebar UX จากเดิม**: ถ้า user เคยเปิดบน mobile แล้วเจอ overlay ตลอด อาจจะคุ้นเคย → แต่นี่เป็นบั๊ก ควรแก้
- **Scaffold dashboard.html**: ถ้ามี sub-project copy dashboard.html → ตรวจว่าไม่ใช่ (Hub ใช้ template แยก)
- **Dark mode**: ตรวจว่า CSS เพิ่มใหม่มี variant สำหรับ `[data-theme="dark"]`
