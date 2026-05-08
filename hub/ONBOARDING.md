# QA Hub Demo — Onboarding

สำหรับคนใหม่ที่เข้ามาใช้/ดูแล Hub — อ่านอันนี้ก่อน, แล้วค่อยไป `CLAUDE.md` ถ้าต้องการ architecture detail

## 60-second mental model

QA Hub Demo คือ **Flask app เดียว** ที่ทำหน้าที่เป็น **หน้า dashboard กลาง** สำหรับจัดการ QA project ทุกตัวใต้ `C:\Automation\`

- **1 โปรเจคใน Hub = 1 folder ใน `C:\Automation\`** (ลงทะเบียนผ่าน UI)
- แต่ละโปรเจคมี type: `full-pipeline` / `manual-testing` / `playwright-only` / `pytest-only` — Hub แสดง stages ต่างกันตาม type
  - `pytest-only` = Python pytest project (ไม่ใช่ TS Playwright) — รัน `python -m pytest` จาก project venv, แสดง stages 5/7/8/9, ใช้ `test-report.html` (pytest-html) แทน Word report
- Hub ไม่ได้รันเทสต์เอง — มัน **orchestrate** (ส่งคำสั่งให้ project scripts รัน) + แสดงผล
- State ทั้งหมดเก็บเป็น JSON: `config.json`, `run_history.json`, `schedules.json`, `bugs/*.json`

## ติดตั้ง + รันครั้งแรก

```powershell
cd C:\Automation\qa-hub-saucedemo
pip install -r requirements.txt
python app.py                      # dev mode — Flask dev server, auto-opens browser
```

**Production**: ใช้ waitress (pure-Python WSGI) แทน Flask dev server
```powershell
python scripts/serve_prod.py                          # 127.0.0.1:8080, 4 threads
python scripts/serve_prod.py --host 0.0.0.0 --port 8080  # expose to LAN
```

Run as Windows service (recommended for 24/7):
```powershell
nssm install QAHubDemo "C:\Python3xx\python.exe" "scripts\serve_prod.py"
nssm set QAHubDemo AppDirectory "C:\Automation\qa-hub-saucedemo"
nssm start QAHubDemo
```

Linux systemd: ดู `scripts/f180-hub.service` (edit user/path, `sudo systemctl enable --now f180-hub`)

**Vue v2 frontend (strangler pattern)** — new features can be written in Vue while legacy UI keeps working:
```powershell
cd frontend
npm install              # one-time
npm run build            # outputs static/dist/* — served by Flask at /v2/
```
- Legacy: <http://localhost:8080/>
- Vue v2: <http://localhost:8080/v2/>
- Dev with HMR: `cd frontend && npm run dev` (proxies /api to localhost:8080)
- See `frontend/README.md` for full guide

**Seed Claude memory ให้ทุก project** (one-time setup for consistent assistant context):
```powershell
python scripts/init_project_memory.py --all   # ทุก registered project + Hub เอง
python scripts/init_project_memory.py --path C:\Automation\BAY\e2e-surveys-bay  # แค่ project เดียว
```
- Copy `user_role.md` + `feedback_principles.md` ไปที่ memory dir ของแต่ละ project
- Hub จะเรียก script นี้อัตโนมัติตอน Add Project ใหม่ (ผ่าน `/api/projects/add`)

**HTTPS + reverse proxy (Production)** — Hub ควรไปอยู่หลัง proxy ใน prod:
- Caddy (ง่ายสุด, auto-cert): ดู `scripts/Caddyfile.example`
- nginx (ถ้ามีอยู่แล้ว): ดู `scripts/nginx.conf.example`
- ทั้งสองรองรับ SSE streams ของ `/api/run/*` และ `/api/system-check` ที่ Hub ใช้

เปิด http://localhost:8080 — Browser จะเปิดเองอัตโนมัติ (dev mode)

**ตั้ง email secret เป็น env var** (ไม่เก็บใน config.json):
```powershell
[Environment]::SetEnvironmentVariable('HUB_SMTP_PASS', '<gmail-app-password>', 'User')
```

**ตั้ง auth password (Production)** — เปิด BasicAuth:
```powershell
[Environment]::SetEnvironmentVariable('HUB_PASSWORD', '<เลือก-password-ให้ทีม>', 'User')
[Environment]::SetEnvironmentVariable('HUB_USERNAME', 'hub', 'User')   # optional, default "hub"
```
- Dev (คนเดียว): ไม่ต้องตั้ง → ไม่มี auth
- Prod (มีคนอื่นเข้าได้): ตั้ง HUB_PASSWORD → startup แสดง `🔐 BasicAuth enabled`

Restart terminal → restart Hub → startup จะแสดงสถานะ secret + auth

## โครงสร้าง (สิ่งที่ต้องรู้)

```
qa-hub-saucedemo/
  app.py                  ← Flask routes + orchestration
  release_gate.py         ← logic ตัดสิน release พร้อมมั้ย
  migrations.py           ← schema migration hooks
  validators.py           ← config.json startup validation
  templates/
    dashboard.html        ← HTML shell (~2,100 lines)
    alpine_demo.html      ← Alpine.js proof-of-concept (/alpine-demo)
  static/
    app.css               ← styles (296 lines)
    app.js                ← dashboard JS (3,900+ lines — section-marked)
  scaffold/               ← templates สำหรับสร้างโปรเจคใหม่
    full-pipeline/
    manual-testing/
  tests/
    test_*.py             ← pytest (fast, ~1.5s)
    e2e/test_*.py         ← Playwright browser tests (marker: e2e)
  .claude/commands/       ← slash commands (/hub-status, /hub-diagnose, ...)
  config.json             ← projects + email (gitignored)
  run_history.json        ← run logs (gitignored)
  schedules.json          ← scheduled runs (gitignored)
  bugs/<project>.json     ← bugs per project (gitignored)
```

## Working with the dashboard UI

หน้า dashboard อยู่ที่ `templates/dashboard.html` + `static/app.js` + `static/app.css` — vanilla HTML/JS/CSS (ไม่มี framework, ไม่มี build step)

### Helper ที่ต้องใช้ (อย่าเขียน fetch/innerHTML ตรงๆ)

**`apiCall(url, opts?)`** — ใช้แทน `fetch()` ทุกครั้งที่เรียก `/api/*`
```javascript
// GET
const data = await apiCall('/api/projects');

// POST JSON
await apiCall('/api/projects/add', {body: {id, name, path, type}});

// Silent mode (caller แสดง error เอง)
try {
  const d = await apiCall('/api/config/email/test', {silent: true, body: payload});
} catch (e) { /* render inline */ }
```
ถ้า API คืน 4xx/5xx → `apiCall` auto-toast error message จาก backend (shape `{error, detail}`) แล้ว throw

**`emptyStateHTML(icon, title, cta?, desc?)`** — ใช้แทน inline "ยังไม่มี X" divs
```javascript
el.innerHTML = emptyStateHTML('📭', 'ยังไม่มี notification', null, 'จะขึ้นเมื่อมี scheduled run เสร็จ');
// พร้อม CTA button:
el.innerHTML = emptyStateHTML('📂', 'ยังไม่มี project', {text: '+ Add', onclick: 'toggleAddForm()'});
```

**`skeletonLinesHTML(count)`** — ใช้แทน "Loading..." text ระหว่างรอ fetch
```javascript
wrap.innerHTML = '<div style="padding:12px">' + skeletonLinesHTML(4) + '</div>';
const data = await apiCall('/api/...');
wrap.innerHTML = renderData(data);  // replaces skeleton
```

**`showToast(msg, type?, duration?)`** — toast notifications
- `type`: `'ok'` (default, green) · `'info'` (blue) · `'err'` (red)
- ใช้สำหรับ user feedback ทั่วไป (apiCall จะเรียกให้อัตโนมัติเมื่อ error)

### Pattern การเขียน feature ใหม่ใน UI

```javascript
async function loadMyFeature() {
  const el = document.getElementById('my-container');
  el.innerHTML = '<div style="padding:12px">' + skeletonLinesHTML(3) + '</div>';
  try {
    const data = await apiCall('/api/my-endpoint');
    if (!data.length) {
      el.innerHTML = emptyStateHTML('🔍', 'ไม่พบข้อมูล', null, 'ลองเปลี่ยน filter');
      return;
    }
    el.innerHTML = data.map(renderItem).join('');
  } catch (e) {
    // apiCall already showed toast. ถ้าต้องการ render inline error:
    el.innerHTML = emptyStateHTML('⚠️', 'โหลดไม่สำเร็จ', {text: 'ลองใหม่', onclick: 'loadMyFeature()'});
  }
}
```

### เพิ่ม route API backend ใหม่

1. เพิ่ม `@app.route('/api/...')` ใน `app.py`
2. Return `jsonify(...)` สำหรับ success, `jsonify({"error": "..."}), 4xx` สำหรับ error
3. Errorhandlers ที่ `app.py` ดูแล 404/405/500 แล้ว → frontend `apiCall` จับได้อัตโนมัติ
4. เพิ่ม integration test ที่ `tests/test_integration_flow.py`
5. ถ้าใช้ใน UI → เพิ่ม caller ใน `static/app.js` ใช้ `apiCall`

## โปรเจคแรกของคุณ (3 นาที)

1. คลิก **Projects** tab → **+ Add Project**
2. กรอก Display Name, เลือก Type, กรอก Base URL
3. เลือกวิธีสร้าง:
   - 📦 **Copy scaffold** — Hub สร้าง folder ให้ + ใส่ template files
   - 🔗 **Clone from Git URL** — ถ้ามี repo อยู่แล้ว
4. คลิก Save → folder ถูกสร้างที่ `C:\Automation\<path-ที่กรอก>\`
5. กลับมาหน้าหลัก → คลิกที่โปรเจค → Pipeline tab เริ่มเห็น stages

## Daily workflow

| สถานการณ์ | ทำอะไร |
|---|---|
| **เช้ามา ดูภาพรวม** | เปิด Hub → Summary tab (ทุกโปรเจค) หรือ `/hub-status` ใน Claude Code |
| **เริ่มทดสอบรอบใหม่** | Projects → เลือกโปรเจค → Pipeline → กด stage 1 → ... → 9 |
| **รัน playwright test** | Pipeline → Stage 5 → เลือก tag (@smoke/@e2e/@regression) + env (UAT/Prod) → Run |
| **พบ bug** | Bug Tracker tab → Add Bug → severity + status |
| **ก่อน release** | Release Readiness Gate tab → ดู ✅/❌ ทุกเกณฑ์ |
| **ตั้ง schedule** | Schedule tab → Add → daily/weekly/cron + tag + env |
| **Sanity check ระบบเอง** | `/hub-structure-check` (เรียกจาก Claude Code) — จับ drift ก่อนสะสม |

## Slash Commands (ใน Claude Code)

| Command | เมื่อไหร่ใช้ |
|---|---|
| `/hub-status` | Daily quick scan |
| `/hub-diagnose` | เมื่อ Hub มีปัญหา |
| `/hub-report` | ทำรายงานให้ทีม |
| `/hub-structure-check` | Weekly / ก่อน release — จับ tech debt |
| `/sync-agents` | หลังแก้ scaffold — กระจายให้ทุก project |

## เมื่อของเสีย — troubleshooting

### Hub ไม่ start
1. รัน `/hub-diagnose` — จะบอกว่า config/schedule/path ไหนเสีย
2. ดู startup output — ถ้ามี `⚠ config.json has N validation issue(s)` → แก้ตามนั้น

### Email ไม่ส่ง
- ตั้ง `HUB_SMTP_PASS` env var แล้วยัง? — ดู startup output `✓ email secrets from env var`
- ทดสอบที่ About → Email Settings → **Test Connection**

### `pip install` fail บนเครื่องใหม่
- ตรวจ Python version ≥ 3.10
- ลบ `__pycache__/` + ติดตั้งใหม่

### Test ล้ม
```bash
python -m pytest tests/ -v           # unit + integration (เร็ว, ~1.5s)
python -m pytest tests/ -m e2e -v    # browser tests (ช้ากว่า, ~8s)
```
- Default run จะ **skip e2e** (marker-based)
- `/hub-structure-check` ก่อน commit ช่วยจับ drift ล่วงหน้า
- ถ้า test ล้มหลัง pull ใหม่ → อย่า force push, สอบถามใน git log ก่อน

### Config.json เสีย
- Startup จะ print `⚠ config.json has N validation issue(s)` — แก้ตามข้อความ
- Restore จาก `backups/hub-backup-<timestamp>.zip` — unzip เอา `config.json` กลับมา

### Backup + restore
Daily snapshot via `scripts/backup.py` (state files → `backups/hub-backup-*.zip`, keep 30 by default):
```powershell
python scripts/backup.py                    # manual
python scripts/backup.py --keep 14          # keep only 14 recent
python scripts/backup.py --dest D:\BackupX  # to different drive
```
Schedule daily at 02:00:
```powershell
schtasks /create /tn "QAHubDemoBackup" /tr "python C:\Automation\qa-hub-saucedemo\scripts\backup.py" /sc daily /st 02:00
```

## สิ่งที่ไม่ควรทำ

- ❌ **Commit `config.json`** — gitignored เพราะมี path ที่อาจมี secret
- ❌ **Commit โดยไม่รัน `pytest tests/`** — กันระเบิดทีมอื่น
- ❌ **`git push --force master`** — master ไม่ควร rewrite
- ❌ **แก้ `app.py` โดยไม่ดู `/hub-structure-check`** — อาจสะสม drift
- ❌ **เขียน `fetch('/api/...')` ตรงๆ ใน UI** — ใช้ `apiCall()` เพื่อให้ error handling ตรงกัน
- ❌ **Inline `<div style="...">ไม่พบ...</div>`** — ใช้ `emptyStateHTML()` เพื่อ style consistency
- ❌ **Hardcode secret ใน `config.json`** — ใช้ env var (`HUB_SMTP_PASS`, `HUB_RESEND_API_KEY`)

## ลึกกว่านี้

- **Architecture + API reference** → `CLAUDE.md`
- **Release gate logic** → `release_gate.py` + `tests/test_api.py`
- **Config validation rules** → `validators.py` + `tests/test_validators.py`
- **Migration policy** → `migrations.py` docstring
- **Integration test patterns** → `tests/test_integration_flow.py`
- **E2E/browser test patterns** → `tests/e2e/test_dashboard_smoke.py`
- **UI helpers (apiCall/emptyStateHTML/skeletonLinesHTML)** → top of `static/app.js`

## ขอความช่วยเหลือ

- Hub bug → เปิด GitHub issue: https://github.com/ArtSadVoice/qa-hub-saucedemo
- Quick question → ลอง `/hub-diagnose` ก่อน, มักเจอสาเหตุ

---

อ่านจบ → ลองใช้จริง 30 นาที → มีอะไรงงให้ feedback กลับเพื่อปรับ doc นี้ต่อไป
