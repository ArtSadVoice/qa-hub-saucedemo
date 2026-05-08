# Hub UX/UI Expert Review

ทบทวน Vue v2 จากมุม UX/UI specialist — issue + actionable recommendations
จัดลำดับตาม **impact × frequency-of-encounter**

## 📐 Visual Design

### Typography
| Issue | Impact | Recommendation |
|---|---|---|
| ไม่มี typographic scale ชัดเจน — h1/h2/h3 ใช้ size ปนกันใน components | 🟡 Medium | Define scale: 11/12/13/14/16/18/22 → use semantic classes (`.text-xs/.text-sm/.text-base`) |
| Font-family ไม่ uniform (some inherit, some explicit `'Cascadia Mono'`) | 🟢 Low | Single `font-family: 'Segoe UI'` global, `font-family: monospace` only on code/data |
| Line-height สั้น (1.4-1.5) ทำให้อ่านยากใน paragraph | 🟢 Low | Body text: 1.6, headings: 1.3 |

### Color
| Issue | Impact | Recommendation |
|---|---|---|
| **Dark mode ไม่มีใน v2** | 🔴 High | port `[data-theme="dark"]` overrides จาก legacy CSS |
| Severity colors ใช้ inconsistent (#C62828 vs #B71C1C) | 🟡 Medium | Centralize: `--severity-critical/high/medium/low` |
| Status colors mix RGB + named (e.g. `#2E7D32` vs `green`) | 🟢 Low | ใช้ hex ทั้งหมดผ่าน CSS variable |
| Primary blue ใช้แล้วแต่จุด (#2E75B6, #1F3864, #1565C0, #2E75B6) | 🟡 Medium | Reduce to 2 shades: `--primary` + `--primary-dark` |

### Spacing
| Issue | Impact | Recommendation |
|---|---|---|
| Hard-coded padding (12px, 14px, 16px, 18px) — ไม่มี spacing scale | 🟡 Medium | 4/8/12/16/24/32 scale — `--space-1` through `--space-6` |
| Card padding ไม่ uniform (12px-22px) | 🟡 Medium | Default `--space-4` (16px), tight `--space-3` (12px) |
| Gap ระหว่าง cards 14px ไม่ rhythm กับ inner spacing | 🟢 Low | Use 16px consistently |

## 🏗️ Information Architecture

### Sidebar
| Issue | Impact | Recommendation |
|---|---|---|
| Group labels เพิ่มแล้วดี — แต่ "Files" group กับ "Tracking" overlap concept | 🟢 Low | Consider: Main / Workflow / Reference |
| Nav-item icon size 15px เล็ก; some emojis อ่านไม่ออก (📥📤 mix kind ของ shape) | 🟡 Medium | Use Lucide/Tabler icons แทน emoji (consistent stroke-weight) |
| ไม่มี collapse mechanism — บนจอแคบ sidebar ทับเนื้อหา | 🟡 Medium | Hamburger toggle → narrow drawer (full sidebar visible on hover) |
| Bug count badge หาย — จากเดิม legacy แสดง "🐛 (3)" | 🔴 High | Add reactive badges to nav items |

### Topbar
| Issue | Impact | Recommendation |
|---|---|---|
| **ไม่มี ⌘K Command Palette** | 🔴 High | Port from legacy — power-user navigation primary |
| **ไม่มี notification bell + polling** | 🔴 High | Bell + dropdown + 60s poll /api/schedules/notifications |
| **ไม่มี dark mode toggle** | 🔴 High | Toggle button + localStorage persistence |
| **ไม่มี global refresh** | 🟡 Medium | Refresh icon ที่ trigger active route's load() |
| Project switcher ไม่ show recent / favorite | 🟢 Low | Add "★ Pin" toggle per project (ออกมาบน) |

### Each tab
| Issue | Impact | Recommendation |
|---|---|---|
| Page title ไม่บอก context (project name หาย) | 🟡 Medium | "Bug Tracker — BAY/e2e-surveys-bay" |
| ไม่มี breadcrumb (Settings → Email tab) | 🟢 Low | Sub-page shouldn't lose top context |
| Tab name "Settings" กว้างเกิน — อยู่ปลาย sidebar | 🟢 Low | Move group label ก่อน Settings: "Configuration" |

## 🎯 Interaction Patterns

### Forms
| Issue | Impact | Recommendation |
|---|---|---|
| Input focus ring ไม่ชัด (เพิ่ง border-color เปลี่ยน) | 🟡 Medium | Add `box-shadow: 0 0 0 3px rgba(46,117,182,.2)` on focus |
| Required fields ไม่ marked (*) | 🟡 Medium | Add asterisk + `aria-required` |
| Validation messages อยู่ใน toast — disconnect from field | 🟡 Medium | Inline error below field on submit-fail |
| Submit buttons disabled แต่ไม่บอกสาเหตุ | 🟡 Medium | Tooltip "fill the title field first" on hover |
| Form reset หลัง save ไม่ smooth (ลด visual feedback) | 🟢 Low | Toast + brief green flash on saved field |

### Tables
| Issue | Impact | Recommendation |
|---|---|---|
| Sort indicators (▲▼) เล็กจนแยกไม่ออก asc/desc | 🟡 Medium | Use heavier glyphs (↑↓) with color |
| ไม่มี hover row → ผู้ใช้งานไม่รู้ว่า row คลิกได้ตรงไหน | 🟡 Medium | `tr:hover { background: #F7FAFF }` |
| Bug list — Edit/Del buttons เล็ก ห่าง 4px เกินไป | 🟢 Low | gap 8px + larger hit area |
| ไม่มี pagination — ถ้า bug 100+ สับสน | 🟡 Medium | ลด default `limit` + "Load more" / virtual scroll |
| Empty state ไม่มี CTA ในบาง view | 🟡 Medium | Add primary button "+ Add" ในทุก empty state |

### Modals
| Issue | Impact | Recommendation |
|---|---|---|
| Esc key ไม่ปิด modal | 🟡 Medium | Add `@keydown.esc="emit('close')"` |
| Focus trap หาย — Tab escape modal ได้ | 🟡 Medium | Use `vue-focus-trap` หรือ implement basic version |
| Auto-focus first field หาย | 🟡 Medium | `<input ref="firstField"> + onMounted nextTick focus()` |
| Modal width fixed 480px — narrow content (e.g. delete confirm) ดูใหญ่เกิน | 🟢 Low | Variant prop: `size: sm/md/lg` |

### Buttons
| Issue | Impact | Recommendation |
|---|---|---|
| Disabled state ไม่ชัด (50% opacity ไม่พอ) | 🟡 Medium | Add `cursor: not-allowed` + grey background |
| Loading state ใน buttons ใช้ text แทน spinner | 🟡 Medium | Inline spinner component |
| Destructive button (Delete) ไม่ distinct enough | 🟡 Medium | Hover: full red background, not just border |
| Button height ไม่ uniform — small variant `padding: 4px 10px`, regular `7px 14px` | 🟢 Low | Define button heights: 24/32/40 |

### Loading states
| Issue | Impact | Recommendation |
|---|---|---|
| Skeleton lines ดี แต่บาง view ใช้ "Loading…" text แทน | 🟡 Medium | Replace all "Loading…" → `skeletonLinesHTML(n)` |
| Initial app boot — blank white screen ก่อน mount | 🟡 Medium | Add splash in `index.html` body (CSS-only) |
| API ช้า → button hang ไม่มี feedback | 🟡 Medium | Auto-spinner หลัง 200ms ใน apiCall |

## ♿ Accessibility (a11y)

| Issue | Impact | Recommendation |
|---|---|---|
| ไม่มี ARIA labels ใน icon-only buttons | 🟡 Medium | Add `aria-label="Refresh"` ทุก icon button |
| Color contrast — `var(--muted)` 6B7C93 บน white = 4.4:1 (AA pass แค่หวยห), borderline | 🟡 Medium | Increase to #5A6B82 (5.2:1) |
| Focus indicators หาย/อ่อน | 🟡 Medium | Visible 3px outline ในทุก interactive element |
| Keyboard navigation — ไม่มี keyboard shortcuts | 🟡 Medium | `?` show help, `g+key` for goto |
| Screen reader — table sorted state ไม่ announce | 🟢 Low | `aria-sort="ascending|descending"` on `<th>` |

## 📱 Responsive / Mobile

| Issue | Impact | Recommendation |
|---|---|---|
| Sidebar fixed 230px ทับเนื้อหาบน mobile | 🟡 Medium | Drawer + hamburger บน width < 768px |
| Tables overflow horizontally → ไม่ scroll smooth | 🟡 Medium | `overflow-x: auto` + sticky first column on mobile |
| Form grid 2-column บีบเกินไปบน narrow | 🟡 Medium | Single column on width < 600px |
| Touch targets เล็กเกิน (button 24px height) | 🟡 Medium | Min 44px sur mobile (Apple HIG) |

## 🎨 Empty/Error/Loading States

### Empty states
| Issue | Recommendation |
|---|---|
| Some views show "Loading…" text ตลอด แม้ load เสร็จ | Use skeleton + final state |
| Empty state ไม่มี **why** info — แค่ "no data" | "No bugs yet. Add one above to get started." + CTA button |
| Filter empty state vs initial empty state เดียวกัน | Differentiate: "No bugs match 'Critical'" vs "No bugs yet" |

### Error states
| Issue | Recommendation |
|---|---|
| Error → toast เดียว → user หาว่าทำอะไรต่อไม่ได้ | Replace toast + show inline retry button in affected view |
| Network error ไม่ distinct จาก server error | Add error banner ที่ top of view: "Lost connection to Hub" |
| 401 Unauthorized → ไม่ redirect login (ถ้า auth on) | Catch 401 → show login modal |

### Loading states
| Issue | Recommendation |
|---|---|
| Initial app boot blank | CSS splash screen ใน body |
| Slow API → ผู้ใช้ click ซ้ำ | Optimistic UI หรือ disable + spinner |

## 🔍 Discoverability

| Feature | Discoverability issue | Fix |
|---|---|---|
| Project switcher | อยู่ใน topbar แต่ icon เดียว | Add "Switch project" hover hint + chevron |
| Edit bug | Edit button เล็ก ห่าง Delete | Group as 1 action menu (⋮) |
| Sort table | ไม่มี hint ว่า column header คลิกได้ | Cursor: pointer + ↕ icon by default |
| Bulk actions | ไม่มี bulk select | Add checkbox column + "Delete selected" |
| Schedule "Run Now" | Tiny ▶ button | Larger, with text label "Run now" |
| Settings sub-tabs | Border-bottom indicator subtle | Tabs ที่ active มี background highlight |

## 🎬 Microinteractions

| Issue | Recommendation |
|---|---|
| Save success → toast disappear ใน 5s | Add green flash on saved field for 1s |
| Delete row → row หาย immediately | Fade-out animation 200ms ก่อนหาย |
| Tab switch → instant | Subtle slide-in 150ms |
| Number changes → instant | Count-up animation for stats (`useCountUp` composable) |

## 🏆 Recommendations — สิ่งที่ควรทำเรียงลำดับ ROI

### Must-have (block production)
1. **Dark mode** (Tier 1) — userbase Hub เป็น dev/QA ที่ใช้ dark theme ตลอด
2. **Notification bell + polling** — สำคัญสำหรับ schedule monitoring
3. **⌘K Command Palette** — productivity boost ใหญ่
4. **Bug count badge in sidebar** — at-a-glance status

### High-value polish
5. **Esc to close modal** + focus trap + auto-focus first field
6. **Hover row** ในทุก table
7. **Visible focus indicators** ทุก interactive element
8. **Inline form validation** แทน toast-only
9. **Empty state CTAs** (เพิ่ม button "+ Add" ในทุก empty)
10. **Sort indicators** ชัดเจนขึ้น (↑↓ + color)

### Long-term
11. **Lucide/Tabler icon set** แทน emoji
12. **Spacing token system** (`--space-*`)
13. **Mobile responsive** (drawer sidebar)
14. **Keyboard shortcuts** ทั้งระบบ
15. **a11y audit** + ARIA polish

## 📊 Quick wins (15-min each)

- Add `cursor: pointer` ทุก clickable element (Edit/Delete/sort headers)
- Add `tr:hover` row highlight
- Add visible focus rings (CSS `:focus-visible`)
- `aria-label` icon-only buttons
- Replace "Loading…" text → skeleton everywhere
- Add empty-state CTAs everywhere

---

หลัง analysis นี้ ผมเริ่มทำ Tier 1 (5 blockers) ในส่วนที่เหลือของ session
