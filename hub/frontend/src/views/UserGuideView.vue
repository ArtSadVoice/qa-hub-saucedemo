<script setup lang="ts">
import { ref } from 'vue'
import { useOnboardingStore } from '@/stores/onboarding'

const onboarding = useOnboardingStore()
const showRestart = ref(false)

const sections = [
  { id: 'getting-started', label: '🚀 เริ่มต้น 5 นาที' },
  { id: 'daily-route',     label: '🌅 Daily Route' },
  { id: 'project-types',   label: '📦 Project Types' },
  { id: 'pipeline',        label: '⚙️ Pipeline (9 stages)' },
  { id: 'release',         label: '🚦 Release Gate' },
  { id: 'bugs',            label: '🐛 Bug Tracker' },
  { id: 'schedule',        label: '📅 Scheduled Runs' },
  { id: 'shortcuts',       label: '⌨️ Keyboard Shortcuts' },
  { id: 'troubleshoot',    label: '🩺 Troubleshooting' },
]

// Topbar (~64px) + quick-nav (~52px) = ~116px sticky overlay. scroll-margin-top
// on each section covers it; we still call scrollIntoView for the smooth animation.
function scroll(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function restartOnboarding() {
  onboarding.reset()
  location.reload()
}
</script>

<template>
  <!-- Quick nav -->
  <nav class="quick-nav">
    <button v-for="s in sections" :key="s.id" class="qn-link" @click="scroll(s.id)">
      {{ s.label }}
    </button>
  </nav>

  <div class="card">
    <div class="card-title">📖 User Guide — สำหรับ QA ที่ใช้ Hub ครั้งแรก</div>
    <p class="lead">
      QA Hub Demo คือ <b>central dashboard</b> สำหรับ QA — รวม test pipeline,
      bug tracking, schedule runner, release readiness ของทุก project ในที่เดียว
    </p>
  </div>

  <!-- Getting started -->
  <div id="getting-started" class="card">
    <h2>🚀 เริ่มต้น 5 นาที</h2>
    <ol class="steps">
      <li>
        <b>เลือก Project</b> จาก dropdown ที่แถบบน — ทุก tab จะ refresh เพื่อแสดงข้อมูล project นั้น
      </li>
      <li>
        ไปที่ <b>Dashboard</b> เพื่อดู snapshot:
        Tests · Pass rate · Open bugs · Trend chart · Scenario summary
      </li>
      <li>
        ถ้าต้องรัน test → ไปที่ <b>Pipeline</b> →
        เลือก tag (@smoke / @e2e / ...) + env (UAT / Prod) → กด <b>▶ Run</b> ของ stage ที่ต้องการ
      </li>
      <li>
        ก่อน release → ไปที่ <b>Release Gate</b> เพื่อตรวจ criteria ทุกข้อ
      </li>
      <li>
        ถ้าเจอ bug → <b>Bug Tracker</b> → <b>+ Add Bug</b> + เลือก severity + assign
      </li>
    </ol>

    <div class="callout tip">
      💡 <b>Tip:</b> กด <kbd>?</kbd> เปิด keyboard shortcuts overlay · <kbd>⌘K</kbd> หรือ <kbd>Ctrl+K</kbd> เปิด command palette
    </div>
  </div>

  <!-- Daily Route / Cycle -->
  <div id="daily-route" class="card">
    <h2>🌅 Daily Route — รอบทำงานต่อวัน</h2>
    <p>
      QA cycle ที่แนะนำ: ทำตาม route นี้ทุกเช้าจะรู้สถานะระบบทั้งหมดใน 5–10 นาที
    </p>

    <h4>☀️ เช้า (08:00–09:00) — ตรวจผลรอบกลางคืน</h4>
    <ol class="steps">
      <li>
        เปิด Dashboard → ดู <b>scheduled run</b> ของเมื่อคืน (default 02:00 บาง project)
        — เห็น pass/fail rate ของ <code>@smoke</code> / <code>slow and statemod</code>
      </li>
      <li>
        ถ้ามีสีแดง → <b>Pipeline → Run History</b> → เปิด log → ระบุ root cause
        (สำหรับ desktop-automation ใช้ <code>/test-triage</code> ใน Claude Code)
      </li>
      <li>
        Bug Tracker → ดู Critical / High ที่ยัง Open — กระจาย assignee + อัปเดต status
      </li>
    </ol>

    <h4>☕ ระหว่างวัน — Develop + Iterate</h4>
    <ol class="steps">
      <li>
        เขียน feature ใหม่ → <code>/write-req &lt;slug&gt; &lt;input&gt;</code> สร้าง
        <code>requirements/&lt;slug&gt;.md</code> → resolve open questions
        → <code>/generate-spec &lt;slug&gt;</code> สร้าง test file
      </li>
      <li>
        ก่อน commit → <code>python scripts/pre_commit_check.py</code>
        (pytest collect + lint + spec↔test pairing)
      </li>
      <li>
        Push → GitHub Actions รัน default suite อัตโนมัติ → ผลขึ้น hub ถ้า set <code>HUB_URL</code>
      </li>
      <li>
        ระหว่าง dev → Pipeline → Stage 5 ▶ <b>Run</b> ทดสอบสด
      </li>
    </ol>

    <h4>🌙 ก่อนกลับ (17:00–18:00) — ตั้ง schedule + ตรวจ release</h4>
    <ol class="steps">
      <li>
        ถ้ามี slow test ใหม่ → Schedule tab → <b>+ Add</b> →
        ตั้ง daily off-peak (เช่น 02:00) ด้วย tag <code>slow and statemod</code>
      </li>
      <li>
        ถ้าจะ release → <b>Release Gate</b> → ตรวจทุก criterion เป็น GO
      </li>
      <li>
        License monitor (desktop-automation): cron วันละครั้ง
        <code>python scripts/check_license_expiry.py</code> →
        warn ที่ ≤ 30 วัน
      </li>
    </ol>

    <h4>📅 รายสัปดาห์ — Audit + Cleanup</h4>
    <ol class="steps">
      <li>
        <code>/coverage-gap</code> ใน Claude Code → audit ว่า requirement
        กับ test ตรงกันทุกอันไหม + มี TCID ครบไหม
      </li>
      <li>
        <code>/hub-structure-check</code> → ตรวจ tech debt / drift ของ hub เอง
      </li>
      <li>
        <code>python scripts/cleanup_logs.py</code> →
        prune logs (7d) + screenshots (30d)
      </li>
    </ol>

    <div class="callout tip">
      💡 <b>เป้าหมาย:</b> สถานะระบบทั้งหมดต้อง <b>green ก่อนคืนนี้</b> →
      schedule วิ่งคืนต่อไป → เช้าได้เห็นสีแดง/เขียวก่อนเริ่มงาน → loop กลับ
    </div>
  </div>

  <!-- Project types -->
  <div id="project-types" class="card">
    <h2>📦 Project Types</h2>
    <p>แต่ละ project มี type ที่กำหนด pipeline stages ที่ใช้ได้:</p>

    <div class="type-grid">
      <div class="type-card">
        <div class="type-icon">🎯</div>
        <h3>full-pipeline</h3>
        <p>TCM Excel + Playwright automation + Word report</p>
        <div class="stages-mini">Stages 1–9 ครบ</div>
      </div>
      <div class="type-card">
        <div class="type-icon">📋</div>
        <h3>manual-testing</h3>
        <p>TCM Excel + ทดสอบ manual + Word report</p>
        <div class="stages-mini">Stages 1, 2, 3, 6, 7, 8, 9 (ซ่อน 4, 5)</div>
      </div>
      <div class="type-card">
        <div class="type-icon">🎭</div>
        <h3>playwright-only</h3>
        <p>Playwright (TS) automation อย่างเดียว ไม่มี TCM</p>
        <div class="stages-mini">Stage 5 เท่านั้น</div>
      </div>
      <div class="type-card">
        <div class="type-icon">🐍</div>
        <h3>pytest-only</h3>
        <p>Python pytest (เช่น Electron via CDP, Appium) — Hub spawn project's own venv</p>
        <div class="stages-mini">Stages 5, 7, 8, 9</div>
      </div>
    </div>
  </div>

  <!-- Pipeline -->
  <div id="pipeline" class="card">
    <h2>⚙️ Pipeline (9 stages)</h2>
    <ol class="stages-list">
      <li><b>Upload Excel TCM</b> — drop ไฟล์ .xlsx ใน <code>input/</code></li>
      <li><b>BA Agent</b> — วิเคราะห์ requirement และสร้าง TCM</li>
      <li><b>Add Charts to Excel</b> — เพิ่ม pie/bar chart</li>
      <li><b>Generate Spec Files</b> (Playwright) — สร้าง <code>.spec.ts</code></li>
      <li><b>Run Tests</b> — รัน Playwright test (รองรับ tag + env)</li>
      <li><b>Screenshot Injection</b> — ใส่ screenshots กลับเข้า Excel</li>
      <li><b>Generate Word Report</b> — สร้าง <code>.docx</code> รายงาน</li>
      <li><b>Open Report</b> — เปิด report ใน browser/app</li>
      <li><b>Download Report</b> — โหลดเป็น attachment</li>
    </ol>

    <div class="callout warn">
      ⚠️ <b>ระวังเลือก Prod environment</b>: test อาจ write data จริง — แนะนำ
      <code>@smoke</code> only + เวลา off-peak (เช่น 06:00)
    </div>

    <h4>Quick actions ที่ Pipeline tab</h4>
    <ul>
      <li><b>⚡ Run All</b> — รัน stage 1–9 ต่อเนื่อง</li>
      <li><b>📤 Send Report</b> — ส่ง Word report ทาง email (กำหนด recipients ใน Settings → Email)</li>
      <li><b>👁️ Watch</b> — auto-rerun เมื่อแก้ไฟล์ (ใช้ตอน dev test ใหม่)</li>
      <li><b>🔁 Re-run failed only</b> — ปรากฏหลัง test fail บางอัน</li>
    </ul>
  </div>

  <!-- Release Gate -->
  <div id="release" class="card">
    <h2>🚦 Release Readiness Gate</h2>
    <p>Hub ตรวจ criteria ก่อน release และให้ verdict:</p>
    <table class="verdict-table">
      <tr><td><span class="verdict-pill GO">GO</span></td><td>ทุก criteria ผ่าน — release ได้</td></tr>
      <tr><td><span class="verdict-pill NOGO">NOGO</span></td><td>มี hard-fail criterion — แก้ก่อน release</td></tr>
      <tr><td><span class="verdict-pill NOT_READY">NOT READY</span></td><td>ยังไม่มี run history — รัน test ก่อน</td></tr>
      <tr><td><span class="verdict-pill SKIP">SKIP</span></td><td>Project อยู่ใน planning หรือ paused phase</td></tr>
    </table>

    <h4>Criteria ตาม project type</h4>
    <ul>
      <li><b>full-pipeline</b>: 8 criteria (TCM uploaded, spec complete, run scope, pass rate, bugs, screenshots, ...)</li>
      <li><b>manual-testing</b>: 6 criteria (TCM, no Not Start, TCM pass rate, no Critical/High bug, report)</li>
      <li><b>playwright-only</b>: 6 criteria (run scope, pass rate, bugs, screenshots, report)</li>
      <li><b>pytest-only</b>: 6 criteria (test executed, run scope, pass rate, bugs, screenshots — drops the TS-specific HTML report check)</li>
    </ul>

    <div class="callout tip">
      💡 <b>Threshold ปรับได้</b>: pass_rate, tcm_pass_rate, screenshot_coverage แก้ใน
      <code>config.json → projects[].gates</code> (default 80%)
    </div>
  </div>

  <!-- Bugs -->
  <div id="bugs" class="card">
    <h2>🐛 Bug Tracker</h2>
    <ul>
      <li><b>+ Add Bug</b> — กรอก title + severity + status</li>
      <li><b>Edit</b> — เปลี่ยน description, assignee, status, severity</li>
      <li><b>👤 Assign</b> — quick-assign + ส่ง email ให้ assignee อัตโนมัติ</li>
      <li><b>📥 Export CSV</b> — โหลด bug list ที่ filter อยู่</li>
      <li><b>Aging</b> — แสดงกี่วันที่ Open (🔴 ≥14d, 🟡 ≥7d)</li>
    </ul>
    <div class="callout tip">
      💡 <b>Severity ที่แนะนำ:</b><br>
      <b>Critical</b> = ระบบใช้ไม่ได้ ·
      <b>High</b> = feature สำคัญพัง ·
      <b>Medium</b> = bug ที่ workaround ได้ ·
      <b>Low</b> = cosmetic / minor
    </div>
    <div class="callout danger">
      🚨 <b>Critical/High open bug = release blocker</b> — Release Gate จะ NOGO
    </div>
  </div>

  <!-- Schedule -->
  <div id="schedule" class="card">
    <h2>📅 Scheduled Runs</h2>
    <ul>
      <li><b>Add Schedule</b> — เลือก project + action + tag + env + schedule type (daily / weekly / cron)</li>
      <li><b>Notify on (override)</b> — กำหนด chat notification rule เฉพาะ schedule นี้</li>
      <li><b>Run Now (▶)</b> — ทดสอบทันทีไม่ต้องรอเวลา</li>
      <li><b>Toggle</b> — เปิด/ปิด schedule</li>
      <li><b>Schedule Log</b> — ดู events ของ scheduler (FIRE / RUN / RESULT / DONE / ERROR)</li>
    </ul>
    <div class="callout warn">
      ⚠️ <b>Prod schedule + non-@smoke tag</b> = Hub จะแสดง confirm dialog เพราะ test อาจ write data จริง
    </div>
    <div class="callout tip">
      💡 <b>ตั้ง chat webhook ก่อน</b> ที่ Settings → Notifications เพื่อรับแจ้งเตือนเข้า Slack/Teams/Discord เมื่อ schedule เสร็จ
    </div>
  </div>

  <!-- Shortcuts -->
  <div id="shortcuts" class="card">
    <h2>⌨️ Keyboard Shortcuts</h2>

    <h4 style="margin-top:0">Global</h4>
    <table class="kb-table">
      <tr><td><kbd>?</kbd></td><td>เปิด shortcut help overlay</td></tr>
      <tr><td><kbd>Ctrl</kbd> + <kbd>K</kbd> <span class="muted">(หรือ <kbd>⌘K</kbd>)</span></td><td>เปิด command palette — ค้นหาทุกอย่าง</td></tr>
      <tr><td><kbd>Esc</kbd></td><td>ปิด modal / palette / overlay</td></tr>
    </table>

    <h4>Navigation (vim-style: type <kbd>g</kbd> แล้วตามด้วยตัวอักษรภายใน 1.2 วินาที)</h4>
    <table class="kb-table">
      <tr><td><kbd>g</kbd> <kbd>d</kbd></td><td>ไป Dashboard</td></tr>
      <tr><td><kbd>g</kbd> <kbd>o</kbd></td><td>ไป All Projects Overview</td></tr>
      <tr><td><kbd>g</kbd> <kbd>p</kbd></td><td>ไป Pipeline</td></tr>
      <tr><td><kbd>g</kbd> <kbd>r</kbd></td><td>ไป Release Gate</td></tr>
      <tr><td><kbd>g</kbd> <kbd>s</kbd></td><td>ไป Schedule</td></tr>
      <tr><td><kbd>g</kbd> <kbd>b</kbd></td><td>ไป Bug Tracker</td></tr>
      <tr><td><kbd>g</kbd> <kbd>a</kbd></td><td>ไป Activity Feed</td></tr>
      <tr><td><kbd>g</kbd> <kbd>j</kbd></td><td>ไป Projects</td></tr>
      <tr><td><kbd>g</kbd> <kbd>i</kbd></td><td>ไป Input Files</td></tr>
      <tr><td><kbd>g</kbd> <kbd>u</kbd></td><td>ไป Output / Reports</td></tr>
      <tr><td><kbd>g</kbd> <kbd>c</kbd></td><td>ไป Screenshots</td></tr>
      <tr><td><kbd>g</kbd> <kbd>y</kbd></td><td>ไป System Check</td></tr>
      <tr><td><kbd>g</kbd> <kbd>h</kbd></td><td>ไป User Guide</td></tr>
      <tr><td><kbd>g</kbd> <kbd>t</kbd></td><td>ไป Settings</td></tr>
    </table>

    <p class="kb-note">
      ⓘ Shortcuts ปิดอัตโนมัติเมื่อ focus อยู่ใน input / textarea / select เพื่อไม่รบกวนการพิมพ์
    </p>
  </div>

  <!-- Troubleshooting -->
  <div id="troubleshoot" class="card">
    <h2>🩺 Troubleshooting</h2>

    <details>
      <summary>Hub ไม่แสดง project ใหม่</summary>
      <p>
        เปิด <b>System Check</b> → กด <b>▶ Run Check</b> ถ้า Hub Config ✗
        ลองเข้า <b>Projects</b> tab + กด <b>🔎 Discover Projects</b> หรือเพิ่มใน config.json โดยตรง
      </p>
    </details>

    <details>
      <summary>Email ไม่ส่ง / Test Connection ล้ม</summary>
      <p>
        Settings → Email → ตรวจ SMTP host/port/user/password<br>
        ถ้า Gmail ใช้ <a href="https://support.google.com/mail/answer/185833" target="_blank" rel="noopener noreferrer">App Password</a> ไม่ใช่ password ปกติ<br>
        หรือเก็บ password ใน env var <code>HUB_SMTP_PASS</code> เพื่อความปลอดภัย
      </p>
    </details>

    <details>
      <summary>Pipeline stage หยุดกลางทาง / hang</summary>
      <p>
        กด <b>⏹ Cancel</b> ใน log card → reload page<br>
        ถ้ายังไม่จบ → restart Hub (Ctrl+C ที่ terminal ที่รัน <code>python app.py</code>)
      </p>
    </details>

    <details>
      <summary>Schedule run ล้มทุกครั้ง</summary>
      <p>
        ดู Schedule Log → หา <code>ERROR</code> หรือ <code>EXCEPT</code> → รายละเอียดอยู่ใน <code>schedule.log</code><br>
        ถ้าเป็น Playwright test fail → เปิด Pipeline → Run Now เพื่อ debug แบบ interactive
      </p>
    </details>

    <details>
      <summary>Dark mode สีเพี้ยน</summary>
      <p>
        ในแถบบนกด theme toggle 2 ครั้ง (Light → Dark → System) — ถ้ายังเพี้ยน clear localStorage:<br>
        DevTools → Application → Local Storage → ลบ <code>fp_theme</code>
      </p>
    </details>

    <details>
      <summary>v2 vs Legacy UI ต่างกัน</summary>
      <p>
        ทั้งคู่ใช้ backend เดียวกัน — สลับได้ผ่าน sidebar footer<br>
        v2 = Vue 3 (modern) · Legacy = vanilla JS (เดิม)<br>
        คำแนะนำ: ใช้ v2 เป็นหลัก, legacy เก็บไว้สำหรับ feature ที่ยังไม่ port
      </p>
    </details>

    <h4 style="margin-top:24px">รัน onboarding tutorial อีกครั้ง</h4>
    <button class="btn" @click="restartOnboarding">🔄 ดู welcome tour ใหม่</button>

    <h4 style="margin-top:28px">มีปัญหา / อยาก feedback?</h4>
    <p>
      เปิด issue ที่ <a href="https://github.com/qa-hub-saucedemo" target="_blank" rel="noopener noreferrer">GitHub</a>
      หรือใส่ใน <code>logs/feedback.md</code> ของ project — ทีมจะอ่านเป็นประจำ.
      ก่อน report bug ลองเปิด <b>System Check</b> เพื่อตรวจ environment ก่อน
      แล้วใส่ผลลัพธ์ (กด 📋 Copy ที่ System Check) ลง issue ด้วย
    </p>
  </div>
</template>

<style scoped>
.quick-nav {
  position: sticky;
  top: 64px;
  background: var(--card);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  padding: 8px;
  margin-bottom: var(--space-4);
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  box-shadow: var(--shadow-sm);
  z-index: 5;
}
.qn-link {
  background: none;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  padding: 6px 12px;
  font-size: 12.5px;
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
}
.qn-link:hover { background: var(--bg); color: var(--text); }

.lead {
  font-size: 15px;
  color: var(--text-secondary);
  line-height: 1.6;
}

/* Each card is a deeplink target. Sticky topbar (~64px) + quick-nav (~52px)
   would otherwise hide the heading after scrollIntoView. */
.card[id] { scroll-margin-top: 130px; }

h2 {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--text);
  margin-bottom: var(--space-4);
}
h4 { font-size: 14px; margin: var(--space-4) 0 var(--space-2); }

.card p, .card ul, .card ol { font-size: 13.5px; line-height: 1.65; color: var(--text-secondary); margin-bottom: var(--space-3); }
.card ul, .card ol { padding-left: 22px; }
.card li { margin-bottom: 4px; }
.steps li { padding-left: 4px; }

.callout {
  padding: 12px 16px;
  border-radius: var(--radius-md);
  font-size: 13px;
  line-height: 1.55;
  margin: var(--space-3) 0;
  border: 1px solid;
}
.callout.tip { background: var(--primary-soft); border-color: rgba(0, 113, 227, 0.2); color: var(--primary-dk, var(--primary)); }
.callout.warn { background: var(--warn-soft); border-color: rgba(255, 159, 10, 0.3); color: var(--warn); }
.callout.danger { background: var(--danger-soft); border-color: rgba(255, 59, 48, 0.3); color: var(--danger); }
[data-theme="dark"] .callout.warn   { color: var(--warn); }
[data-theme="dark"] .callout.danger { color: var(--danger); }

.type-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--space-3);
  margin-top: var(--space-3);
}
.type-card {
  background: var(--bg);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  text-align: center;
}
.type-icon { font-size: 36px; margin-bottom: var(--space-2); }
.type-card h3 { font-size: 14px; margin-bottom: 4px; color: var(--text); }
.type-card p { font-size: 12.5px; color: var(--muted); margin-bottom: var(--space-3); }
.stages-mini {
  font-size: 11px;
  background: var(--card);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  padding: 4px 8px;
  display: inline-block;
  color: var(--text);
}

.stages-list { counter-reset: stage; padding-left: 0; list-style: none; }
.stages-list li {
  counter-increment: stage;
  padding-left: 32px;
  position: relative;
  margin-bottom: 6px;
}
.stages-list li::before {
  content: counter(stage);
  position: absolute;
  left: 0; top: 0;
  width: 22px; height: 22px;
  background: var(--primary);
  color: white;
  border-radius: 50%;
  font-size: 11px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}

.verdict-table, .kb-table { border-collapse: collapse; width: 100%; margin: var(--space-3) 0; }
.verdict-table td, .kb-table td { padding: 8px 12px; border-bottom: 1px solid var(--border-soft); font-size: 13px; }
.verdict-table td:first-child, .kb-table td:first-child { width: 140px; white-space: nowrap; }
.verdict-pill {
  font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: var(--radius-md);
  display: inline-block;
}
.verdict-pill.GO { background: var(--success-soft); color: var(--success); }
.verdict-pill.NOGO { background: var(--danger-soft); color: var(--danger); }
.verdict-pill.NOT_READY { background: var(--warn-soft); color: var(--warn); }
.verdict-pill.SKIP { background: var(--bg); color: var(--muted); }
[data-theme="dark"] .verdict-pill.GO        { color: var(--success); }
[data-theme="dark"] .verdict-pill.NOGO      { color: var(--danger); }
[data-theme="dark"] .verdict-pill.NOT_READY { color: var(--warn); }

kbd {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-xs);
  padding: 1px 7px;
  font-family: "SF Mono", "Cascadia Mono", monospace;
  font-size: 11px;
  color: var(--text);
  display: inline-block;
}
.muted { color: var(--muted); font-size: 11px; }
.kb-note {
  font-size: 12px;
  color: var(--muted);
  background: var(--bg);
  border-left: 3px solid var(--border);
  padding: 8px 12px;
  border-radius: var(--radius-xs);
  margin-top: var(--space-3) !important;
}

details {
  margin-bottom: var(--space-2);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  background: var(--card);
  overflow: hidden;
}
details summary {
  padding: 12px 16px;
  font-weight: 600;
  font-size: 13.5px;
  cursor: pointer;
  list-style: none;
  display: flex;
  align-items: center;
  user-select: none;
}
details summary::before {
  content: '›';
  display: inline-block;
  margin-right: 8px;
  transition: transform var(--duration-fast) var(--ease);
  font-size: 16px;
  color: var(--muted);
}
details[open] summary::before { transform: rotate(90deg); }
details summary::-webkit-details-marker { display: none; }
details p {
  padding: 0 16px 14px 36px;
  margin: 0;
  font-size: 13px;
  line-height: 1.65;
  color: var(--text-secondary);
}
</style>
