<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import { apiCall } from '@/api/client'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { useProjectStore } from '@/stores/projects'
import TipBanner from '@/components/TipBanner.vue'
import { nextOccurrences, parseCron } from '@/utils/cron'

interface Schedule {
  id: string
  project_id: string
  project_name?: string
  action: 'tests' | 'generate' | 'inject' | 'add-charts'
  tag: string                                              // stored without leading "@" — server prepends
  env: 'uat' | 'prod'
  schedule_type: 'daily' | 'weekly' | 'cron'
  time?: string
  weekday?: number
  cron?: string
  enabled: boolean
  notify_on?: string[]
  created_at: string
  last_run?: string | null
  last_status?: string | null
}

const projects = useProjectStore()
const toast = useToast()
const { confirm } = useConfirm()

const schedules = ref<Schedule[]>([])
const loading = ref(true)
const refreshing = ref(false)

// ── Filter / search ────────────────────────────────────────────────
const filterProject = ref('')
const filterStatus = ref<'all' | 'enabled' | 'disabled' | 'failing'>('all')
const search = ref('')

const filteredSchedules = computed(() => {
  const q = search.value.trim().toLowerCase()
  return schedules.value.filter((s) => {
    if (filterProject.value && s.project_id !== filterProject.value) return false
    if (filterStatus.value === 'enabled'  && !s.enabled) return false
    if (filterStatus.value === 'disabled' && s.enabled)  return false
    if (filterStatus.value === 'failing'  && !(s.last_status || '').toLowerCase().startsWith('error')) return false
    if (q) {
      const hay = `${s.project_name || ''} ${s.project_id} ${s.action} ${s.tag} ${s.env} ${s.cron || ''}`.toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  })
})

const FORM_DEFAULTS = {
  project_id: '',
  action: 'tests' as Schedule['action'],
  tag: 'all',
  env: 'uat' as Schedule['env'],
  schedule_type: 'daily' as Schedule['schedule_type'],
  time: '08:00',
  weekday: 1,
  cron: '0 8 * * *',
  notify_on: '' as '' | 'error-only' | 'fail-error' | 'all',
}
const form = reactive({ ...FORM_DEFAULTS })

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const isProdRisky = computed(() => form.env === 'prod' && form.tag !== 'smoke')

async function load() {
  loading.value = true
  refreshing.value = true
  try {
    schedules.value = (await apiCall<Schedule[]>('/api/schedules')) || []
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

async function addSchedule() {
  if (!form.project_id) { toast.show('เลือก project ก่อน', 'warn'); return }
  if (isProdRisky.value) {
    const ok = await confirm({
      title: '🚨 Prod + non-smoke tag',
      desc: 'test อาจ write data จริงบน Production — ยืนยันที่จะเพิ่ม schedule นี้?',
      danger: true,
      okLabel: 'Add anyway',
    })
    if (!ok) return
  }

  // Tag stored without leading "@" — scheduler prepends when launching playwright,
  // matching the convention used by Pipeline /api/run/tests.
  const body: Record<string, unknown> = {
    project_id:    form.project_id,
    action:        form.action,
    tag:           form.tag,
    env:           form.env,
    schedule_type: form.schedule_type,
    time:          form.time,
    weekday:       form.weekday,
    cron:          form.cron,
  }
  if (form.notify_on) {
    body.notify_on = form.notify_on === 'all' ? ['all']
                   : form.notify_on === 'error-only' ? ['error']
                   : ['fail', 'error']
  }
  try {
    await apiCall('/api/schedules/add', { body })
    toast.show('✅ Schedule added', 'ok')
    // Reset form so the user can clearly tell the action succeeded — preserve project_id
    // so adding several schedules for the same project doesn't require re-selecting.
    const keepProject = form.project_id
    Object.assign(form, FORM_DEFAULTS, { project_id: keepProject })
    await load()
  } catch { /* apiCall toasted */ }
}

async function toggleSchedule(s: Schedule) {
  try {
    await apiCall('/api/schedules/toggle', { body: { id: s.id } })
    await load()
  } catch { /* apiCall toasted */ }
}

async function deleteSchedule(s: Schedule) {
  const ok = await confirm({
    title: 'Delete schedule?',
    desc: `${s.action} · ${s.tag || 'all'} · ${s.env} on ${s.project_name || s.project_id}`,
    danger: true,
    okLabel: 'Delete',
  })
  if (!ok) return
  try {
    await apiCall('/api/schedules/delete', { body: { id: s.id } })
    toast.show('Schedule deleted', 'ok')
    await load()
  } catch { /* apiCall toasted */ }
}

async function runNow(s: Schedule) {
  const ok = await confirm({
    title: 'Run now?',
    desc: `Run "${s.action} ${s.tag || 'all'}" on ${s.project_name || s.project_id} เดี๋ยวนี้`,
    okLabel: '▶ Run',
  })
  if (!ok) return
  try {
    await apiCall('/api/schedules/run-now', { body: { id: s.id } })
    toast.show('Running… check log when done', 'ok')
    setTimeout(load, 2000)
  } catch { /* apiCall toasted */ }
}

// ── Schedule summary + next-run preview ────────────────────────────
const scheduleSummary = (s: Schedule) => {
  if (s.schedule_type === 'daily')  return `Daily ${s.time}`
  if (s.schedule_type === 'weekly') return `Every ${WEEKDAYS[s.weekday ?? 0]} ${s.time}`
  return `cron: ${s.cron}`
}

// Compute next fire time. Daily/weekly are simple arithmetic; cron uses the
// parser in @/utils/cron which walks minute-by-minute up to a 4-year cap.
function nextRun(s: Schedule): { ts: Date; relative: string } | null {
  if (!s.enabled) return null
  if (s.schedule_type === 'cron') {
    if (!s.cron) return null
    const occ = nextOccurrences(s.cron, new Date(), 1)
    return occ.length ? { ts: occ[0], relative: relTime(occ[0]) } : null
  }
  if (!s.time) return null
  const [hh, mm] = s.time.split(':').map(Number)
  if (isNaN(hh) || isNaN(mm)) return null
  const now = new Date()
  const candidate = new Date(now)
  candidate.setHours(hh, mm, 0, 0)
  if (s.schedule_type === 'daily') {
    if (candidate <= now) candidate.setDate(candidate.getDate() + 1)
  } else if (s.schedule_type === 'weekly') {
    const targetDow = ((s.weekday ?? 0) + 1) % 7   // 0=Mon → Date.getDay() 1=Mon
    let daysAhead = (targetDow - candidate.getDay() + 7) % 7
    if (daysAhead === 0 && candidate <= now) daysAhead = 7
    candidate.setDate(candidate.getDate() + daysAhead)
  }
  return { ts: candidate, relative: relTime(candidate) }
}

// Cron preview popover state — keyed by schedule id so two rows don't clash
const cronPreviewOpen = ref<string>('')
function toggleCronPreview(id: string) {
  cronPreviewOpen.value = cronPreviewOpen.value === id ? '' : id
}
function cronNextFires(expr?: string): Date[] {
  if (!expr) return []
  return nextOccurrences(expr, new Date(), 5)
}
function cronExpressionValid(expr?: string): boolean {
  return !!expr && parseCron(expr) !== null
}
function fmtFireTime(d: Date): string {
  return d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function relTime(target: Date): string {
  const diffMs = target.getTime() - Date.now()
  if (diffMs <= 0) return 'now'
  const mins  = Math.round(diffMs / 60_000)
  if (mins < 60) return `in ${mins}m`
  const hours = Math.floor(mins / 60)
  const minR  = mins % 60
  if (hours < 24) return minR ? `in ${hours}h ${minR}m` : `in ${hours}h`
  const days = Math.floor(hours / 24)
  return `in ${days}d`
}

// ── Status badge → CSS class (was: hex inline styles) ───────────────
function statusClass(s: Schedule): string {
  const v = (s.last_status || '').toLowerCase()
  if (!v) return 's-mute'
  if (v.startsWith('ok')) return 's-ok'
  if (v.startsWith('error')) return 's-fail'
  return 's-warn'
}

// ── Schedule log ──────────────────────────────────────────────────
const logLines = ref<string[]>([])
const showLog = ref(false)

async function loadLog() {
  try {
    const r = await apiCall<{ lines: string[] }>('/api/schedules/log', { silent: true })
    logLines.value = r?.lines || []
  } catch {
    logLines.value = []
  }
}

function logLineClass(line: string): string {
  if (/\bERROR\b|\bEXCEPT\b/i.test(line)) return 'log-err'
  if (/\bDONE\b.*ok\b/i.test(line)) return 'log-ok'
  if (/\bRESULT\b|\bRUN\b/i.test(line)) return 'log-run'
  return ''
}

onMounted(async () => {
  if (!projects.all.length) await projects.load()
  if (!form.project_id && projects.current) form.project_id = projects.current
  load()
  loadLog()
})
</script>

<template>
  <TipBanner id="schedule-intro" variant="tip">
    <b>Tip:</b> ตั้ง chat webhook ที่ <code>Settings → Notifications</code> ก่อน
    เพื่อรับแจ้งเตือนเมื่อ scheduled run เสร็จเข้า Slack / Teams / Discord.
    ใช้ "Notify on (override)" เพื่อตั้งกฎเฉพาะ schedule นี้
  </TipBanner>
  <TipBanner id="schedule-prod-warn" variant="warn" persistent v-if="form.env === 'prod' && form.tag !== 'smoke'">
    <b>🚨 Prod + non-smoke:</b> Hub จะแสดง confirm dialog ก่อน save —
    test อาจ write data จริงบน Production
  </TipBanner>

  <!-- Add Schedule -->
  <div class="card">
    <div class="card-title">➕ Add Schedule</div>
    <div class="form-grid form-grid-wide">
      <div class="field">
        <label>Project</label>
        <select v-model="form.project_id">
          <option value="" disabled>Select project…</option>
          <option v-for="p in projects.all" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
      </div>
      <div class="field">
        <label>Action</label>
        <select v-model="form.action">
          <option value="tests">Run Tests</option>
          <option value="generate">Generate TCM</option>
          <option value="inject">Inject Screenshots</option>
          <option value="add-charts">Add Charts to Excel</option>
        </select>
      </div>
      <div class="field">
        <label>Tag</label>
        <select v-model="form.tag">
          <option value="all">all</option>
          <option value="smoke">@smoke</option>
          <option value="e2e">@e2e</option>
          <option value="regression">@regression</option>
          <option value="visual">@visual</option>
        </select>
      </div>
      <div class="field">
        <label>Env</label>
        <select v-model="form.env" :class="{ 'env-prod': form.env === 'prod' }">
          <option value="uat">🟢 UAT</option>
          <option value="prod">🔴 Prod</option>
        </select>
      </div>
      <div class="field">
        <label>Schedule type</label>
        <select v-model="form.schedule_type">
          <option value="daily">Daily</option>
          <option value="weekly">Weekly</option>
          <option value="cron">Cron expression</option>
        </select>
      </div>
      <div v-if="form.schedule_type === 'daily' || form.schedule_type === 'weekly'" class="field">
        <label>Time (HH:MM)</label>
        <input v-model="form.time" type="time" />
      </div>
      <div v-if="form.schedule_type === 'weekly'" class="field">
        <label>Day of week</label>
        <select v-model.number="form.weekday">
          <option v-for="(d, i) in WEEKDAYS" :key="i" :value="i">{{ d }}</option>
        </select>
      </div>
      <div v-if="form.schedule_type === 'cron'" class="field" style="grid-column: span 2">
        <label style="display:flex;align-items:center;gap:8px">
          Cron expression
          <span v-if="!cronExpressionValid(form.cron) && form.cron" class="cron-bad">⚠ invalid syntax</span>
          <span v-else-if="cronExpressionValid(form.cron)" class="cron-good">✓ valid · next: {{ cronNextFires(form.cron)[0] ? fmtFireTime(cronNextFires(form.cron)[0]) : 'never matches' }}</span>
        </label>
        <input v-model="form.cron" placeholder="0 8 * * *" />
        <div v-if="cronExpressionValid(form.cron) && cronNextFires(form.cron).length > 1" class="cron-preview-inline">
          Upcoming: {{ cronNextFires(form.cron).slice(1, 4).map(fmtFireTime).join(' · ') }}
        </div>
      </div>
      <div class="field">
        <label>Notify on (override)</label>
        <select v-model="form.notify_on">
          <option value="">Use global setting</option>
          <option value="error-only">Error only</option>
          <option value="fail-error">Fail + error</option>
          <option value="all">All events</option>
        </select>
      </div>
    </div>
    <div v-if="isProdRisky" class="warn-banner">
      ⚠️ Production + non-smoke = test อาจ write data จริง — Hub จะ confirm ก่อน save
    </div>
    <button class="btn btn-primary" @click="addSchedule" style="margin-top:12px">➕ Add Schedule</button>
  </div>

  <!-- Schedule list -->
  <div class="card">
    <div class="card-title" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
      📅 Scheduled Runs
      <span class="count">{{ filteredSchedules.length }}/{{ schedules.length }}</span>

      <input v-model="search" type="text" placeholder="Search…" class="search" />
      <select v-model="filterProject" class="filter-sel">
        <option value="">All projects</option>
        <option v-for="p in projects.all" :key="p.id" :value="p.id">{{ p.name }}</option>
      </select>
      <div class="seg">
        <button class="seg-btn" :class="{ active: filterStatus === 'all' }" @click="filterStatus = 'all'">All</button>
        <button class="seg-btn" :class="{ active: filterStatus === 'enabled' }" @click="filterStatus = 'enabled'">On</button>
        <button class="seg-btn" :class="{ active: filterStatus === 'disabled' }" @click="filterStatus = 'disabled'">Off</button>
        <button class="seg-btn" :class="{ active: filterStatus === 'failing' }" @click="filterStatus = 'failing'">Failing</button>
      </div>
      <button class="btn btn-sm" :disabled="refreshing" @click="load">{{ refreshing ? '⏳' : '↻' }} Refresh</button>
    </div>

    <div v-if="loading" class="empty">Loading…</div>
    <div v-else-if="!schedules.length" class="empty">
      <div class="empty-icon">⏰</div>
      <div><b>ยังไม่มี schedule</b></div>
      <div class="empty-hint">เพิ่มข้างบนเพื่อให้ Hub รัน tests อัตโนมัติ</div>
    </div>
    <div v-else-if="!filteredSchedules.length" class="empty">
      <div class="empty-icon">🔍</div>
      <div>ไม่พบ schedule ที่ตรงกับ filter</div>
      <button class="btn btn-sm" @click="search = ''; filterProject = ''; filterStatus = 'all'" style="margin-top:8px">
        Clear filters
      </button>
    </div>
    <table v-else class="table-stack">
      <thead>
        <tr>
          <th>Project</th>
          <th style="width:140px">Action / Tag</th>
          <th style="width:70px">Env</th>
          <th style="width:170px">When · Next</th>
          <th style="width:200px">Last run</th>
          <th style="width:60px">On</th>
          <th style="width:130px">Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="s in filteredSchedules" :key="s.id" :class="{ 'row-prod': s.env === 'prod', 'row-off': !s.enabled }">
          <td data-label="Project"><b>{{ s.project_name || s.project_id }}</b></td>
          <td data-label="Action / Tag">
            {{ s.action }}
            <span class="tag-pill">@{{ s.tag === 'all' ? 'all' : s.tag }}</span>
          </td>
          <td data-label="Env"><span class="env-pill" :class="s.env">{{ s.env === 'prod' ? '🔴 PROD' : '🟢 UAT' }}</span></td>
          <td data-label="When · Next" class="when-cell">
            <div class="when">
              {{ scheduleSummary(s) }}
              <button v-if="s.schedule_type === 'cron'" class="cron-toggle"
                      @click.stop="toggleCronPreview(s.id)"
                      :title="cronPreviewOpen === s.id ? 'Hide preview' : 'Show next 5 fires'">
                {{ cronPreviewOpen === s.id ? '▾' : '▸' }}
              </button>
            </div>
            <div v-if="nextRun(s)" class="when-next" :title="nextRun(s)!.ts.toLocaleString()">
              ⏱ {{ nextRun(s)!.relative }}
            </div>
            <div v-else-if="!s.enabled" class="when-next muted">paused</div>
            <div v-else-if="s.schedule_type === 'cron' && !cronExpressionValid(s.cron)" class="when-next bad">
              ⚠ invalid cron
            </div>
            <div v-if="cronPreviewOpen === s.id && cronNextFires(s.cron).length" class="cron-preview">
              <div class="cron-preview-label">Next 5 fires</div>
              <div v-for="(d, i) in cronNextFires(s.cron)" :key="i" class="cron-preview-row">
                {{ fmtFireTime(d) }}
              </div>
            </div>
          </td>
          <td data-label="Last run">
            <span v-if="s.last_run" class="last-run">{{ s.last_run }}</span>
            <span v-else class="muted small">never</span>
            <span v-if="s.last_status" class="status-badge" :class="statusClass(s)">{{ s.last_status }}</span>
          </td>
          <td data-label="On">
            <label class="toggle">
              <input type="checkbox" :checked="s.enabled" @change="toggleSchedule(s)">
              <span class="slider"></span>
            </label>
          </td>
          <td data-label="">
            <button class="btn btn-sm" @click="runNow(s)" title="Run now">▶</button>
            <button class="btn btn-sm btn-danger" @click="deleteSchedule(s)" title="Delete" style="margin-left:4px">Del</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- Schedule log viewer -->
  <div class="card">
    <div class="card-title" style="display:flex;align-items:center;gap:8px">
      📜 Schedule Log
      <span class="count">last {{ logLines.length }} events</span>
      <button class="btn btn-sm" @click="showLog = !showLog" style="margin-left:auto">
        {{ showLog ? 'Hide' : 'Show' }}
      </button>
      <button v-if="showLog" class="btn btn-sm" @click="loadLog">↻ Refresh</button>
    </div>
    <div v-if="showLog" class="log-wrap">
      <div v-if="logLines.length" class="log" role="log">
        <div v-for="(line, i) in logLines.slice().reverse()" :key="i"
             class="log-line" :class="logLineClass(line)">{{ line || ' ' }}</div>
      </div>
      <div v-else class="empty">ไม่มี log entries</div>
    </div>
  </div>
</template>

<style scoped>
.count { font-size: 12px; color: var(--muted); font-weight: 400; }
.muted { color: var(--muted); }
.muted.small { font-size: 11px; }

.form-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; align-items: end; }
.field label { display: block; font-size: 11px; color: var(--muted); margin-bottom: 4px; font-weight: 600; }
.field input, .field select { width: 100%; }

@media (max-width: 640px) {
  /* Stack Add Schedule form: 4-col → 1-col */
  .form-grid { grid-template-columns: 1fr; gap: 10px; }
  /* Filter bar: search goes full-width on its own row */
  .search { max-width: 100%; min-width: 0; margin-left: 0; flex: 1 1 100%; }
  .filter-sel { max-width: 100%; flex: 1 1 calc(50% - 8px); }
}
.field select.env-prod { color: var(--danger); font-weight: 700; }
.warn-banner {
  background: var(--warn-soft);
  border: 1px solid rgba(255, 159, 10, 0.3);
  color: var(--warn);
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  margin-top: 12px;
}
[data-theme="dark"] .warn-banner { color: var(--warn); }

/* Filter bar */
.search {
  font-size: 12.5px;
  min-width: 140px;
  max-width: 200px;
  margin-left: auto;
}
.filter-sel {
  font-size: 12px;
  max-width: 180px;
  width: auto;
}
.seg {
  display: inline-flex;
  background: var(--bg);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  padding: 3px;
}
.seg-btn {
  background: transparent;
  border: none;
  font: inherit;
  font-size: 11.5px;
  color: var(--muted);
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease);
}
.seg-btn:hover { color: var(--text); }
.seg-btn.active {
  background: var(--card);
  color: var(--text);
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}

.empty {
  text-align: center;
  padding: 36px 20px;
  color: var(--muted);
}
.empty-icon { font-size: 32px; margin-bottom: 10px; opacity: .55; }
.empty b { color: var(--text); font-weight: 600; }
.empty-hint { font-size: 12.5px; margin-top: 6px; }

/* Table */
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 8px 10px; border-bottom: 1px solid var(--border-soft); text-align: left; vertical-align: middle; }
th { background: var(--bg); font-size: 11px; text-transform: uppercase; color: var(--muted); letter-spacing: .3px; }
.row-prod { background: var(--danger-soft); }
.row-off  { opacity: 0.55; }

.tag-pill {
  display: inline-block;
  font-size: 11px;
  background: var(--bg);
  color: var(--muted);
  padding: 1px 7px;
  border-radius: var(--radius-md);
  margin-left: 4px;
  font-family: "SF Mono", monospace;
}
.env-pill { font-size: 10.5px; font-weight: 700; padding: 2px 7px; border-radius: 10px; }
.env-pill.uat  { background: var(--success-soft); color: var(--success); }
.env-pill.prod { background: var(--danger);       color: white; }
[data-theme="dark"] .env-pill.uat { color: var(--success); }

.when-cell { vertical-align: top; }
.when      { font-size: 12.5px; color: var(--text); font-weight: 500; display: flex; align-items: center; gap: 6px; }
.when-next { font-size: 11px;   color: var(--primary); margin-top: 2px; font-weight: 600; }
.when-next.muted { color: var(--muted); font-weight: 400; }
.when-next.bad   { color: var(--danger); font-weight: 600; }
.last-run  { font-family: "SF Mono", monospace; font-size: 11.5px; color: var(--muted); }

.cron-toggle {
  background: none;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-xs);
  font: inherit;
  font-size: 10px;
  color: var(--muted);
  width: 18px; height: 18px;
  cursor: pointer;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.cron-toggle:hover { color: var(--text); border-color: var(--primary); }
.cron-preview {
  margin-top: 6px;
  padding: 6px 9px;
  background: var(--bg);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  font-family: "SF Mono", monospace;
  font-size: 11px;
  color: var(--text-secondary, var(--text));
}
.cron-preview-label {
  font-size: 9.5px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--muted);
  font-weight: 700;
  margin-bottom: 3px;
}
.cron-preview-row { line-height: 1.5; }
.cron-preview-inline {
  font-size: 11px;
  color: var(--muted);
  font-family: "SF Mono", monospace;
  margin-top: 4px;
}
.cron-good { color: var(--success); font-size: 11px; font-weight: 500; font-family: inherit; }
.cron-bad  { color: var(--danger); font-size: 11px; font-weight: 500; font-family: inherit; }
[data-theme="dark"] .cron-good { color: var(--success); }

.status-badge {
  font-size: 10.5px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 10px;
  margin-left: 6px;
}
.s-mute { background: var(--bg);          color: var(--muted); border: 1px solid var(--border-soft); }
.s-ok   { background: var(--success-soft); color: var(--success); }
.s-warn { background: var(--warn-soft);    color: var(--warn); }
.s-fail { background: var(--danger-soft);  color: var(--danger); }
[data-theme="dark"] .s-ok   { color: var(--success); }
[data-theme="dark"] .s-warn { color: var(--warn); }

.btn-sm { padding: 4px 10px; font-size: 12px; }

/* Log block — same architecture as Pipeline log to avoid the whitespace gap */
.log-wrap { max-height: 380px; overflow-y: auto; }
.log {
  background: #0d1117;  /* stylelint-disable-line color-no-hex */
  color: #c9d1d9;  /* stylelint-disable-line color-no-hex */
  padding: 12px 14px;
  border-radius: var(--radius-sm);
  font-family: 'Cascadia Mono', 'Consolas', monospace;
  font-size: 11.5px;
  line-height: 1.5;
  margin: 0;
}
.log-line {
  white-space: pre-wrap;
  word-break: break-word;
  min-height: 1em;
}
.log-err { color: #F85149; }  /* stylelint-disable-line color-no-hex */
.log-ok  { color: #56D364; }  /* stylelint-disable-line color-no-hex */
.log-run { color: #58A6FF; }  /* stylelint-disable-line color-no-hex */

/* Toggle switch */
.toggle { position: relative; display: inline-block; width: 38px; height: 20px; }
.toggle input { opacity: 0; width: 0; height: 0; }
.slider {
  position: absolute;
  cursor: pointer;
  inset: 0;
  background: var(--border);
  border-radius: 20px;
  transition: var(--duration-fast) var(--ease);
}
.slider:before {
  position: absolute;
  content: "";
  height: 14px; width: 14px;
  left: 3px; top: 3px;
  background: white;
  border-radius: 50%;
  transition: var(--duration-fast) var(--ease);
}
.toggle input:checked + .slider { background: var(--success); }
.toggle input:checked + .slider:before { transform: translateX(18px); }
</style>
