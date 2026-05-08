<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { apiCall } from '@/api/client'
import { useToast } from '@/composables/useToast'

interface AuditEntry {
  ts: string
  user: string
  ip?: string
  action: string
  details: Record<string, unknown>
}

const toast = useToast()
const entries = ref<AuditEntry[]>([])
const filter = ref('')
const search = ref('')
const loading = ref(true)
const refreshing = ref(false)
const limit = ref(200)

async function load() {
  if (entries.value.length === 0) loading.value = true
  refreshing.value = true
  try {
    const r = await apiCall<{ entries: AuditEntry[]; count: number }>(
      `/api/audit?limit=${limit.value}${filter.value ? '&action=' + filter.value : ''}`,
      { silent: true }
    )
    entries.value = r.entries || []
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

// Free-text search across action + user + ip + details (client-side after fetch)
const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return entries.value
  return entries.value.filter((e) => {
    const hay = [
      e.action, e.user, e.ip || '',
      ...Object.entries(e.details || {}).map(([k, v]) => `${k}=${stringifyDetail(v)}`),
    ].join(' ').toLowerCase()
    return hay.includes(q)
  })
})

// Group by day with smart labels (Today / Yesterday / fallback to date)
interface DayGroup { key: string; label: string; items: AuditEntry[] }
const grouped = computed<DayGroup[]>(() => {
  const groups: Record<string, AuditEntry[]> = {}
  for (const e of filtered.value.slice().reverse()) {
    const day = (e.ts || '').slice(0, 10)
    if (!groups[day]) groups[day] = []
    groups[day].push(e)
  }
  // Sort newest first
  return Object.entries(groups)
    .sort((a, b) => b[0].localeCompare(a[0]))
    .map(([key, items]) => ({ key, label: dayLabel(key), items }))
})

function dayLabel(ymd: string): string {
  if (!ymd) return ''
  const today = new Date(); today.setHours(0, 0, 0, 0)
  const yest  = new Date(today); yest.setDate(yest.getDate() - 1)
  const fmt = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  if (ymd === fmt(today)) return 'Today'
  if (ymd === fmt(yest))  return 'Yesterday'
  // E.g. "Mon, 28 Apr"
  const d = new Date(ymd + 'T00:00:00')
  return d.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short' })
}

// Relative time — "just now / 3m / 2h / 4d"
function relTime(ts: string): string {
  if (!ts) return ''
  const t = Date.parse(ts.replace(' ', 'T'))
  if (isNaN(t)) return ''
  const diffSec = Math.floor((Date.now() - t) / 1000)
  if (diffSec < 30) return 'just now'
  if (diffSec < 60) return `${diffSec}s ago`
  const m = Math.floor(diffSec / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  return `${d}d ago`
}

// Action → semantic category (CSS class) instead of fragile keyword match.
// Categories chosen so future action names map cleanly:
//   create | update | destroy | config | external | other
function actionCategory(action: string): string {
  const a = action || ''
  if (/\.(remove|delete|drop|clear|purge)\b/.test(a)) return 'destroy'
  if (/\.(add|create|save|send)\b/.test(a))           return 'create'
  if (/\.(update|toggle|edit|rename)\b/.test(a))      return 'update'
  if (/^config\./.test(a))                            return 'config'
  if (/^ai\./.test(a) || /^notif/.test(a))            return 'external'
  return 'other'
}

function actionIcon(a: string): string {
  if (a.startsWith('project.add'))    return '➕'
  if (a.startsWith('project.update')) return '✏️'
  if (a.startsWith('project.remove')) return '🗑️'
  if (a.startsWith('schedule.'))      return '📅'
  if (a.startsWith('config.'))        return '⚙️'
  if (a.startsWith('ai.'))            return '🤖'
  if (a.startsWith('notif'))          return '🔔'
  return '📋'
}

// Render arbitrary detail value safely — primitives stay as-is, objects/arrays
// become condensed JSON so users don't see "[object Object]".
function stringifyDetail(v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') return String(v)
  try { return JSON.stringify(v) } catch { return String(v) }
}

async function copyEntry(e: AuditEntry) {
  try {
    await navigator.clipboard.writeText(JSON.stringify(e, null, 2))
    toast.show('📋 Copied entry as JSON', 'ok')
  } catch {
    toast.show('Copy failed — clipboard API blocked', 'err')
  }
}

onMounted(load)
</script>

<template>
  <div class="card">
    <div class="card-title" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
      📋 Activity Feed
      <span class="count">{{ filtered.length }}/{{ entries.length }} entries</span>
      <button class="btn btn-sm" :disabled="refreshing" @click="load" style="margin-left:auto">
        {{ refreshing ? '⏳' : '↻' }} Refresh
      </button>
    </div>
    <p class="sub">
      Audit trail สำหรับทุกการเปลี่ยนแปลง — backed by <code>/api/audit</code> · grouped by day.
    </p>

    <div class="toolbar">
      <input v-model="search" type="text" placeholder="Search action, user, ip, detail values…" class="search" />
      <select v-model="filter" @change="load" class="filter-sel">
        <option value="">All actions</option>
        <option value="project.">project.* (add / update / remove)</option>
        <option value="schedule.">schedule.* (add / delete / toggle)</option>
        <option value="config.">config.* (email / branding / notif / ai)</option>
        <option value="ai.">ai.* (test plan generation)</option>
      </select>
      <select v-model.number="limit" @change="load" class="filter-sel" title="Max entries to fetch">
        <option :value="50">50 entries</option>
        <option :value="200">200 entries</option>
        <option :value="500">500 entries</option>
      </select>
    </div>
  </div>

  <div v-if="loading" class="card empty">Loading…</div>

  <div v-else-if="!entries.length" class="card empty">
    <div class="empty-icon">📭</div>
    <div><b>ยังไม่มี audit log</b></div>
    <div class="empty-hint">Hub จะเริ่มบันทึกเมื่อมีการเปลี่ยนแปลงในระบบ (เพิ่ม project, แก้ config, ฯลฯ)</div>
  </div>

  <div v-else-if="!filtered.length" class="card empty">
    <div class="empty-icon">🔍</div>
    <div>ไม่พบ event ที่ตรงกับ "<b>{{ search }}</b>"</div>
    <button class="btn btn-sm" @click="search = ''" style="margin-top:10px">Clear search</button>
  </div>

  <div v-for="g in grouped" :key="g.key" class="card day-group">
    <div class="day-header">
      <span>{{ g.label }}</span>
      <span class="day-date">{{ g.key }}</span>
      <span class="day-count">· {{ g.items.length }} event{{ g.items.length === 1 ? '' : 's' }}</span>
    </div>
    <div v-for="(e, i) in g.items" :key="g.key + '-' + i" class="event-row" :class="'cat-' + actionCategory(e.action)">
      <div class="event-icon">{{ actionIcon(e.action) }}</div>
      <div class="event-body">
        <div class="event-action">{{ e.action }}</div>
        <div class="event-meta">
          <span class="user-tag">
            <b>{{ e.user }}</b>
            <span v-if="e.ip && e.ip !== '-'" class="ip-tag">{{ e.ip }}</span>
          </span>
          <span class="ts-rel" :title="e.ts">{{ relTime(e.ts) }}</span>
        </div>
        <div v-if="e.details && Object.keys(e.details).length" class="event-details">
          <code v-for="(v, k) in e.details" :key="k" class="kv">{{ k }}=<b>{{ stringifyDetail(v) }}</b></code>
        </div>
      </div>
      <button class="copy-btn" @click="copyEntry(e)" title="Copy as JSON">📋</button>
    </div>
  </div>
</template>

<style scoped>
.sub { color: var(--muted); font-size: 13px; margin-bottom: 12px; }
.count { font-size: 12px; color: var(--muted); font-weight: 400; }

.toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.search {
  flex: 1;
  min-width: 220px;
  max-width: 380px;
  font-size: 12.5px;
}
.filter-sel { font-size: 12px; max-width: 240px; width: auto; }

.empty {
  text-align: center;
  padding: 40px 20px;
  color: var(--muted);
}
.empty-icon { font-size: 36px; margin-bottom: 10px; opacity: .55; }
.empty b { color: var(--text); font-weight: 600; }
.empty-hint { font-size: 12.5px; margin-top: 6px; }

.day-group { padding: 12px 16px; }
.day-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: -0.01em;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-soft);
}
.day-date {
  font-family: "SF Mono", monospace;
  font-size: 11px;
  font-weight: 500;
  color: var(--muted);
  text-transform: none;
  letter-spacing: 0;
}
.day-count { font-size: 11px; font-weight: 400; color: var(--muted); }

.event-row {
  display: flex;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-soft);
  position: relative;
}
.event-row:last-child { border-bottom: none; }

.event-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  font-size: 16px;
  flex-shrink: 0;
  background: var(--bg);
}

.event-body { flex: 1; min-width: 0; }
.event-action {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
  font-family: "SF Mono", monospace;
}
.event-meta {
  font-size: 12px;
  display: flex;
  gap: 14px;
  align-items: center;
  margin-top: 3px;
  flex-wrap: wrap;
}
.user-tag b { color: var(--text); }
.ip-tag {
  margin-left: 6px;
  font-family: "SF Mono", monospace;
  font-size: 11px;
  color: var(--muted);
}
.ts-rel {
  color: var(--muted);
  font-size: 11.5px;
  cursor: help;
  border-bottom: 1px dotted var(--border);
}

.event-details {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.kv {
  font-size: 11px;
  background: var(--bg);
  padding: 2px 8px;
  border-radius: var(--radius-xs);
  color: var(--text-secondary, var(--text));
  border: 1px solid var(--border-soft);
  font-family: "SF Mono", monospace;
  word-break: break-word;
  max-width: 100%;
}

.copy-btn {
  background: transparent;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-xs);
  width: 28px;
  height: 28px;
  font-size: 13px;
  cursor: pointer;
  opacity: 0;
  flex-shrink: 0;
  transition: all var(--duration-fast) var(--ease);
  color: var(--muted);
}
.event-row:hover .copy-btn { opacity: 1; }
.copy-btn:hover {
  background: var(--primary-soft);
  color: var(--primary);
  border-color: var(--primary);
}

/* Semantic action categories — replaces fragile keyword color match */
.cat-create  .event-icon { background: var(--success-soft); color: var(--success); }
.cat-update  .event-icon { background: var(--primary-soft); color: var(--primary); }
.cat-destroy .event-icon { background: var(--danger-soft);  color: var(--danger); }
.cat-config  .event-icon { background: rgba(106, 27, 154, 0.12); color: #6A1B9A; }  /* stylelint-disable-line color-no-hex */
.cat-external .event-icon { background: rgba(21, 101, 192, 0.12); color: var(--primary); }
.cat-other   .event-icon { background: var(--bg); color: var(--muted); }

.cat-create  .event-action { color: var(--success); }
.cat-update  .event-action { color: var(--primary); }
.cat-destroy .event-action { color: var(--danger); }
.cat-config  .event-action { color: #6A1B9A; }  /* stylelint-disable-line color-no-hex */
.cat-external .event-action { color: var(--primary); }

[data-theme="dark"] .cat-create  .event-icon,
[data-theme="dark"] .cat-create  .event-action { color: var(--success); }
[data-theme="dark"] .cat-config   .event-icon,
[data-theme="dark"] .cat-config   .event-action { color: #C792EA; background: rgba(199, 146, 234, 0.15); }  /* stylelint-disable-line color-no-hex */
[data-theme="dark"] .cat-external .event-icon,
[data-theme="dark"] .cat-external .event-action { color: #82AAFF; background: rgba(130, 170, 255, 0.15); }  /* stylelint-disable-line color-no-hex */
</style>
