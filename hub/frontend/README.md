# QA Hub Demo — Vue 3 Frontend (Strangler)

Vue 3 + Vite + TypeScript + Pinia + vue-router · served at `/v2/*` while the
legacy vanilla-JS dashboard at `/` keeps running unchanged.

## เริ่มใช้งาน

```bash
cd frontend
npm install              # one-time
npm run build            # produces static/dist/* — served by Flask at /v2/
```

แล้วเปิด <http://localhost:8080/v2/> (Hub ต้อง run อยู่)

## Dev workflow (hot reload)

```bash
# Terminal 1 — Hub backend
cd C:\Automation\qa-hub-saucedemo
python app.py

# Terminal 2 — Vue dev server with HMR
cd frontend
npm run dev              # http://localhost:5173
```

`vite.config.ts` proxies `/api/*` ไปที่ `http://localhost:8080` ดังนั้น Vue dev
server ใช้ API จริงของ Hub ได้ทันที

## โครงสร้าง

```
frontend/
  package.json
  vite.config.ts            # build → ../static/dist/, base /static/dist/
  tsconfig*.json
  index.html                # Vite entry
  src/
    main.ts                 # Pinia + router + mount('#app')
    App.vue                 # shell — sidebar + topbar + RouterView
    styles/app.css          # ported subset of static/app.css
    router/index.ts         # vue-router with /v2/ base
    api/
      client.ts             # apiCall<T>() — TS port of vanilla helper
      types.ts              # Bug, Project, Severity, ...
    composables/useToast.ts # toast state + show/dismiss
    components/
      Layout/Sidebar.vue    # nav + back-to-legacy link
      Layout/Topbar.vue     # title + toast container
      ui/Toast.vue          # toast notifications
    views/
      DashboardView.vue     # placeholder + live /api/hub/health stats
      BugTrackerView.vue    # full CRUD against /api/bugs (the strangler PoC)
```

## Adding a new tab

1. Create `src/views/MyTabView.vue`
2. Register a route in `src/router/index.ts`
3. Add a nav item in `src/components/Layout/Sidebar.vue`
4. Build (`npm run build`) — Hub serves the new route at `/v2/<path>`

## Migrating an existing tab from vanilla

1. Identify the API endpoints it uses (ส่วนใหญ่อยู่ใน `static/app.js`)
2. Build a Vue view + components mirroring the layout
3. Add the route in `router/index.ts`
4. When the v2 version is feature-parity → switch the legacy nav-item to
   redirect to `/v2/<path>` (or just leave both for a transition period)

## Build verification

CI builds the Vue app on every push (see `.github/workflows/tests.yml`,
`vue-build` job) — local-only build success is not enough.

## ลบ Vue ออกถ้าไม่ใช้

```bash
rm -rf frontend/ static/dist/
# Remove /v2/ route from app.py
# Done — vanilla UI keeps working
```
