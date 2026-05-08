<script setup lang="ts">
import { ref, computed, onMounted, reactive, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { apiCall } from '@/api/client'
import type { Bug, Severity, BugStatus } from '@/api/types'
import { useToast } from '@/composables/useToast'
import { useProjectStore } from '@/stores/projects'
import { useBugsStore } from '@/stores/bugs'
import BugEditModal from '@/components/BugEditModal.vue'
import BugAssignModal from '@/components/BugAssignModal.vue'
import BugMetrics from '@/components/BugMetrics.vue'
import BugKanban from '@/components/BugKanban.vue'
import TipBanner from '@/components/TipBanner.vue'
import { useConfirm } from '@/composables/useConfirm'

const { confirm } = useConfirm()
const showMetrics = ref(false)
type ViewMode = 'table' | 'kanban'
const viewMode = ref<ViewMode>('table')

const projects = useProjectStore()
const bugsStore = useBugsStore()
const SEVERITIES: Severity[] = ['Critical', 'High', 'Medium', 'Low']
const SEV_RANK: Record<Severity, number> = { Critical: 4, High: 3, Medium: 2, Low: 1 }
const STATUSES: BugStatus[] = ['Open', 'Fixed', 'Closed']

type SortBy = 'severity' | 'status' | 'created_at'
const sortBy = ref<SortBy>('severity')
const sortDir = ref<'asc' | 'desc'>('desc')

const editingBug = ref<Bug | null>(null)
const assigningBug = ref<Bug | null>(null)

const bugs = ref<Bug[]>([])
const loading = ref(true)

// Filters
const filterSeverity = ref<Severity | ''>('')
const filterStatus   = ref<BugStatus | 'all'>('Open')   // Default to "Open" — that's the workflow most users want
const filterAssignee = ref<string>('')                  // empty = all
const search         = ref('')

const form = reactive({
  title: '',
  severity: 'High' as Severity,
  status: 'Open' as BugStatus,
  description: '',
})
const showFormDesc = ref(false)

const toast = useToast()

const assignees = computed<string[]>(() => {
  const set = new Set<string>()
  for (const b of bugs.value) if (b.assignee) set.add(b.assignee)
  return Array.from(set).sort()
})

const filteredBugs = computed(() => {
  const q = search.value.trim().toLowerCase()
  let list = bugs.value
  if (filterSeverity.value) list = list.filter((b) => b.severity === filterSeverity.value)
  if (filterStatus.value !== 'all') list = list.filter((b) => b.status === filterStatus.value)
  if (filterAssignee.value) {
    list = filterAssignee.value === '__none__'
      ? list.filter((b) => !b.assignee)
      : list.filter((b) => b.assignee === filterAssignee.value)
  }
  if (q) {
    list = list.filter((b) =>
      (b.title + ' ' + (b.description || '') + ' ' + (b.assignee || '')).toLowerCase().includes(q)
    )
  }
  // Sort
  const dir = sortDir.value === 'asc' ? 1 : -1
  return list.slice().sort((a, b) => {
    let cmp = 0
    if (sortBy.value === 'severity') cmp = SEV_RANK[a.severity] - SEV_RANK[b.severity]
    else if (sortBy.value === 'status') cmp = a.status.localeCompare(b.status)
    else cmp = (a.created_at || '').localeCompare(b.created_at || '')
    return cmp * dir
  })
})

function setSort(col: SortBy) {
  if (sortBy.value === col) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  else {
    sortBy.value = col
    sortDir.value = 'desc'
  }
}

function sortIndicator(col: SortBy): string {
  if (sortBy.value !== col) return ' ↕'
  return sortDir.value === 'asc' ? ' ↑' : ' ↓'
}

// Stat tiles now show open / total per severity so user can see actual workload
function countBySeverity(s: Severity): { open: number; total: number } {
  let open = 0, total = 0
  for (const b of bugs.value) {
    if (b.severity !== s) continue
    total++
    if (b.status === 'Open') open++
  }
  return { open, total }
}

function ageDays(b: Bug): number | null {
  if (!b.created_at) return null
  const t = Date.parse(b.created_at.replace(' ', 'T'))
  if (isNaN(t)) return null
  return Math.floor((Date.now() - t) / 86400000)
}

function ageClass(b: Bug): string {
  const d = ageDays(b)
  if (d === null || b.status !== 'Open') return 'age-mute'
  if (d >= 14) return 'age-bad'
  if (d >= 7)  return 'age-mid'
  return ''
}

// "Today 14:30" / "Yesterday 09:00" / "Mon 28 Apr" relative date — full ts on hover
function fmtCreated(ts?: string): string {
  if (!ts) return '—'
  const t = Date.parse(ts.replace(' ', 'T'))
  if (isNaN(t)) return ts
  const d = new Date(t)
  const today = new Date(); today.setHours(0, 0, 0, 0)
  const yest  = new Date(today); yest.setDate(yest.getDate() - 1)
  const dDay = new Date(d); dDay.setHours(0, 0, 0, 0)
  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  if (dDay.getTime() === today.getTime()) return `Today ${time}`
  if (dDay.getTime() === yest.getTime())  return `Yesterday ${time}`
  return d.toLocaleDateString([], { day: 'numeric', month: 'short' }) + ' ' + time
}

async function loadBugs() {
  if (!projects.current) return
  loading.value = true
  try {
    bugs.value = (await apiCall<Bug[]>(`/api/bugs?p=${projects.current}`)) || []
    // Drop selections for bugs that no longer exist (deleted in another tab, etc)
    const valid = new Set(bugs.value.map((b) => b.id))
    for (const id of Array.from(selected.value)) if (!valid.has(id)) selected.value.delete(id)
  } finally {
    loading.value = false
  }
}

// ── Bulk-action selection ──────────────────────────────────────────────
const selected = ref<Set<string>>(new Set())
const allFilteredSelected = computed(() =>
  filteredBugs.value.length > 0 && filteredBugs.value.every((b) => selected.value.has(b.id))
)
const someFilteredSelected = computed(() =>
  filteredBugs.value.some((b) => selected.value.has(b.id))
)
function toggleOne(id: string) {
  if (selected.value.has(id)) selected.value.delete(id)
  else selected.value.add(id)
}
function toggleAllFiltered() {
  if (allFilteredSelected.value) {
    for (const b of filteredBugs.value) selected.value.delete(b.id)
  } else {
    for (const b of filteredBugs.value) selected.value.add(b.id)
  }
}
function clearSelection() { selected.value.clear() }

const bulkBusy = ref(false)
async function bulkSetStatus(newStatus: BugStatus) {
  if (!selected.value.size || !projects.current) return
  const targets = bugs.value.filter((b) => selected.value.has(b.id) && b.status !== newStatus)
  if (!targets.length) {
    toast.show(`ทั้งหมดเป็น ${newStatus} อยู่แล้ว`, 'info')
    return
  }
  const ok = await confirm({
    title: `Set ${targets.length} bug(s) → ${newStatus}?`,
    desc: `จะอัปเดต status ของ ${targets.length} bug ที่เลือก`,
    okLabel: `Set → ${newStatus}`,
  })
  if (!ok) return
  bulkBusy.value = true
  let done = 0, failed = 0
  try {
    for (const b of targets) {
      try {
        await apiCall('/api/bugs/update', {
          silent: true,
          body: { project_id: projects.current, id: b.id, status: newStatus },
        })
        b.status = newStatus
        done++
      } catch { failed++ }
    }
    toast.show(`✅ Updated ${done}${failed ? ` · ✗ ${failed} failed` : ''}`, failed ? 'warn' : 'ok')
    bugsStore.load()
  } finally {
    bulkBusy.value = false
    if (done) clearSelection()
  }
}

async function bulkDelete() {
  if (!selected.value.size || !projects.current) return
  const targets = bugs.value.filter((b) => selected.value.has(b.id))
  const ok = await confirm({
    title: `Delete ${targets.length} bug(s)?`,
    desc: `<b>This action cannot be undone.</b><br>${targets.length} bug จะถูกลบถาวร.`,
    icon: '🗑️', okLabel: 'Delete', danger: true,
  })
  if (!ok) return
  bulkBusy.value = true
  let done = 0, failed = 0
  try {
    for (const b of targets) {
      try {
        await apiCall('/api/bugs/delete', {
          silent: true,
          body: { project_id: projects.current, id: b.id },
        })
        done++
      } catch { failed++ }
    }
    toast.show(`🗑 Deleted ${done}${failed ? ` · ✗ ${failed} failed` : ''}`, failed ? 'warn' : 'ok')
    await loadBugs()
    bugsStore.load()
  } finally {
    bulkBusy.value = false
    clearSelection()
  }
}

async function addBug() {
  const title = form.title.trim()
  if (!title || !projects.current) return
  try {
    await apiCall('/api/bugs/add', {
      body: {
        project_id: projects.current,
        title,
        severity: form.severity,
        status: form.status,
        description: form.description.trim() || undefined,
      },
    })
    form.title = ''
    form.description = ''
    showFormDesc.value = false
    toast.show('Bug added', 'ok')
    await loadBugs()
    bugsStore.load()
  } catch { /* apiCall toasted */ }
}

async function deleteBug(id: string) {
  const target = bugs.value.find((b) => b.id === id)
  const ok = await confirm({
    title: 'Delete this bug?',
    desc: target ? `<b>${target.title}</b><br>This action cannot be undone.` : 'This action cannot be undone.',
    icon: '🗑️', okLabel: 'Delete', danger: true,
  })
  if (!ok) return
  try {
    await apiCall('/api/bugs/delete', { body: { project_id: projects.current, id } })
    toast.show('Bug deleted', 'ok')
    await loadBugs()
    bugsStore.load()
  } catch { /* apiCall toasted */ }
}

async function changeStatus(b: Bug, newStatus: BugStatus) {
  if (b.status === newStatus) return
  try {
    await apiCall('/api/bugs/update', {
      body: { project_id: projects.current, id: b.id, status: newStatus },
    })
    toast.show(`Status → ${newStatus}`, 'ok')
    b.status = newStatus
    bugsStore.load()
  } catch { /* apiCall toasted */ }
}

async function changeSeverity(b: Bug, newSev: Severity) {
  if (b.severity === newSev) return
  try {
    await apiCall('/api/bugs/update', {
      body: { project_id: projects.current, id: b.id, severity: newSev },
    })
    toast.show(`Severity → ${newSev}`, 'ok')
    b.severity = newSev
  } catch { /* apiCall toasted */ }
}

async function duplicateBug(b: Bug) {
  try {
    await apiCall('/api/bugs/add', {
      body: {
        project_id: projects.current,
        title:    `(copy) ${b.title}`,
        severity: b.severity,
        status:   'Open',
        description: b.description || '',
      },
    })
    toast.show('Bug duplicated', 'ok')
    await loadBugs()
    bugsStore.load()
  } catch { /* apiCall toasted */ }
}

function exportExcel() {
  if (!projects.current) return
  window.open(`/api/bugs/export?p=${projects.current}`, '_blank')
}

function exportCSV() {
  if (!bugs.value.length) return
  const cols = ['id', 'title', 'severity', 'status', 'assignee', 'created_at', 'description']
  const csvRows = [cols.join(',')]
  for (const b of filteredBugs.value) {
    const row = cols.map((c) => {
      const v = (b as Record<string, unknown>)[c] ?? ''
      const s = String(v).replace(/"/g, '""')
      return /[,\n"]/.test(s) ? `"${s}"` : s
    })
    csvRows.push(row.join(','))
  }
  const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const stamp = new Date().toISOString().slice(0, 10)
  a.download = `bugs_${projects.current}_${stamp}.csv`
  a.click()
  URL.revokeObjectURL(url)
  toast.show(`📥 Exported ${filteredBugs.value.length} bug(s)`, 'ok')
}

// Apply Command Palette / deep-link query params on mount.
//   ?severity=Critical    → preset severity filter
//   ?status=Open          → preset status filter (or 'all')
//   ?assignee=email       → preset assignee filter
//   ?action=add           → focus the title input so user can start typing
const route = useRoute()
function applyQueryParams() {
  const q = route.query
  const sev = String(q.severity || '')
  if (sev && (SEVERITIES as string[]).includes(sev)) filterSeverity.value = sev as Severity
  const st = String(q.status || '')
  if (st === 'all' || (STATUSES as string[]).includes(st)) filterStatus.value = st as BugStatus | 'all'
  const asn = String(q.assignee || '')
  if (asn) filterAssignee.value = asn
  if (q.action === 'add') {
    nextTick(() => {
      const titleInput = document.querySelector<HTMLInputElement>('.card .form-grid input')
      titleInput?.focus()
    })
  }
}

onMounted(async () => {
  if (!projects.all.length) await projects.load()
  loadBugs()
  applyQueryParams()
})
watch(() => projects.current, loadBugs)
// Re-apply when navigating from Command Palette while already on /bugs
watch(() => route.query, applyQueryParams)
</script>

<template>
  <TipBanner id="bugs-intro" variant="tip">
    <b>Severity guideline:</b> Critical = ระบบใช้ไม่ได้ · High = feature สำคัญพัง · Medium = workaround ได้ · Low = cosmetic.
    <b>Critical/High open bugs จะ block release</b> — Release Gate จะ NOGO
  </TipBanner>

  <!-- Add bug form -->
  <div class="card">
    <div class="card-title">+ Add Bug</div>
    <div class="form-grid form-grid-wide">
      <div class="field">
        <label>Title</label>
        <input v-model="form.title" @keyup.enter="addBug" placeholder="Bug title…" />
      </div>
      <div class="field">
        <label>Severity</label>
        <select v-model="form.severity">
          <option v-for="s in SEVERITIES" :key="s" :value="s">{{ s }}</option>
        </select>
      </div>
      <div class="field">
        <label>Status</label>
        <select v-model="form.status">
          <option v-for="s in STATUSES" :key="s">{{ s }}</option>
        </select>
      </div>
      <button class="btn btn-primary" @click="addBug" :disabled="!form.title.trim()">Add</button>
    </div>
    <div class="form-extra">
      <button v-if="!showFormDesc" type="button" class="link-btn" @click="showFormDesc = true">
        + Add description (steps to reproduce, expected, etc.)
      </button>
      <textarea v-else v-model="form.description" rows="3"
                placeholder="Steps to reproduce / expected vs actual / environment…" />
    </div>
  </div>

  <!-- Filters + stats -->
  <div class="card">
    <div class="card-title" style="display:flex;align-items:center">
      Filter &amp; Stats
      <div style="margin-left:auto;display:flex;gap:6px">
        <button class="btn btn-sm" @click="exportCSV" :disabled="!filteredBugs.length"
                title="Download visible bugs as CSV">📥 CSV</button>
        <button class="btn btn-sm" @click="exportExcel" :disabled="!bugs.length"
                title="Download all bugs as Excel">📊 Excel</button>
      </div>
    </div>

    <!-- Severity tiles: now color-coded + show open/total -->
    <div class="stat-row">
      <div v-for="s in SEVERITIES" :key="s" class="stat" :class="`sev-${s}`">
        <div class="n">
          {{ countBySeverity(s).open }}<span class="n-sub">/{{ countBySeverity(s).total }}</span>
        </div>
        <div class="l">{{ s }} <span class="l-sub">open / total</span></div>
      </div>
    </div>

    <!-- Filter bar -->
    <div class="filter-bar">
      <input v-model="search" type="text" placeholder="Search title / description / assignee…" class="search" />
      <div class="seg" role="group" aria-label="Status">
        <button class="seg-btn" :class="{ active: filterStatus === 'Open' }"   @click="filterStatus = 'Open'">🟠 Open</button>
        <button class="seg-btn" :class="{ active: filterStatus === 'Fixed' }"  @click="filterStatus = 'Fixed'">🟢 Fixed</button>
        <button class="seg-btn" :class="{ active: filterStatus === 'Closed' }" @click="filterStatus = 'Closed'">⚪ Closed</button>
        <button class="seg-btn" :class="{ active: filterStatus === 'all' }"    @click="filterStatus = 'all'">All</button>
      </div>
      <select v-model="filterSeverity" class="filter-sel">
        <option value="">All severities</option>
        <option v-for="s in SEVERITIES" :key="s" :value="s">{{ s }}</option>
      </select>
      <select v-if="assignees.length" v-model="filterAssignee" class="filter-sel">
        <option value="">All assignees</option>
        <option value="__none__">Unassigned</option>
        <option v-for="a in assignees" :key="a" :value="a">👤 {{ a }}</option>
      </select>
      <button class="btn btn-sm" @click="showMetrics = !showMetrics">
        {{ showMetrics ? 'Hide' : 'Show' }} 📊 metrics
      </button>
      <button class="btn btn-sm" @click="loadBugs">↻ Refresh</button>
    </div>
  </div>

  <BugMetrics v-if="showMetrics" :bugs="bugs" />

  <!-- View toggle: Table / Kanban -->
  <div class="view-toggle">
    <button class="vt-btn" :class="{ active: viewMode === 'table' }" @click="viewMode = 'table'">📋 Table</button>
    <button class="vt-btn" :class="{ active: viewMode === 'kanban' }" @click="viewMode = 'kanban'">📦 Kanban</button>
  </div>

  <!-- Kanban view -->
  <BugKanban v-if="viewMode === 'kanban' && projects.current"
             :bugs="filteredBugs"
             :project-id="projects.current"
             @edit="(b) => editingBug = b"
             @changed="loadBugs" />

  <!-- Bulk action bar — only when selection exists -->
  <div v-if="viewMode === 'table' && selected.size > 0" class="bulk-bar">
    <span><b>{{ selected.size }}</b> selected</span>
    <button class="btn btn-sm" :disabled="bulkBusy" @click="bulkSetStatus('Closed')">⚪ Close</button>
    <button class="btn btn-sm" :disabled="bulkBusy" @click="bulkSetStatus('Fixed')">🟢 Mark Fixed</button>
    <button class="btn btn-sm" :disabled="bulkBusy" @click="bulkSetStatus('Open')">🟠 Re-open</button>
    <button class="btn btn-sm btn-danger" :disabled="bulkBusy" @click="bulkDelete">🗑 Delete</button>
    <button class="btn btn-sm" :disabled="bulkBusy" @click="clearSelection" style="margin-left:auto">× Clear</button>
  </div>

  <!-- Bug list (table) -->
  <div v-if="viewMode === 'table'" class="card">
    <div class="card-title">Bug List <span class="count">({{ filteredBugs.length }})</span></div>
    <div v-if="loading" class="empty">Loading…</div>
    <div v-else-if="filteredBugs.length === 0 && (filterSeverity || filterStatus !== 'all' || filterAssignee || search)" class="empty">
      <div class="empty-icon">🔍</div>
      <div>No bugs match the current filter</div>
      <button class="btn btn-sm" style="margin-top:10px"
              @click="filterSeverity = ''; filterStatus = 'all'; filterAssignee = ''; search = ''">
        Clear filters
      </button>
    </div>
    <div v-else-if="filteredBugs.length === 0" class="empty">
      <div class="empty-icon">🎉</div>
      <div><b>No bugs yet</b></div>
      <div class="empty-hint">Add one above to start tracking</div>
    </div>
    <table v-else>
      <thead>
        <tr>
          <th style="width:32px">
            <input type="checkbox" :checked="allFilteredSelected"
                   :indeterminate.prop="someFilteredSelected && !allFilteredSelected"
                   @change="toggleAllFiltered"
                   :title="allFilteredSelected ? 'Deselect all' : 'Select all visible'" />
          </th>
          <th style="width:40px">#</th>
          <th>Title</th>
          <th style="width:110px;cursor:pointer" @click="setSort('severity')">Severity{{ sortIndicator('severity') }}</th>
          <th style="width:110px;cursor:pointer" @click="setSort('status')">Status{{ sortIndicator('status') }}</th>
          <th style="width:60px">Aging</th>
          <th style="width:130px;cursor:pointer" @click="setSort('created_at')">Created{{ sortIndicator('created_at') }}</th>
          <th style="width:130px">Assignee</th>
          <th style="width:140px"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(b, i) in filteredBugs" :key="b.id" :class="{ selected: selected.has(b.id) }">
          <td>
            <input type="checkbox" :checked="selected.has(b.id)" @change="toggleOne(b.id)"
                   @click.stop />
          </td>
          <td>{{ i + 1 }}</td>
          <td>
            <b>{{ b.title }}</b>
            <span v-if="b.description" class="desc-icon" :title="b.description.slice(0, 220)">📝</span>
          </td>
          <td>
            <select class="sev-inline" :class="`sev-${b.severity}`"
                    :value="b.severity"
                    @change="changeSeverity(b, ($event.target as HTMLSelectElement).value as Severity)"
                    @click.stop>
              <option v-for="s in SEVERITIES" :key="s" :value="s">{{ s }}</option>
            </select>
          </td>
          <td>
            <select class="status-inline" :class="`s-${b.status}`"
                    :value="b.status"
                    @change="changeStatus(b, ($event.target as HTMLSelectElement).value as BugStatus)"
                    @click.stop>
              <option v-for="s in STATUSES" :key="s">{{ s }}</option>
            </select>
          </td>
          <td class="aging" :class="ageClass(b)">
            <template v-if="ageDays(b) !== null">{{ ageDays(b) }}d</template>
            <template v-else>—</template>
          </td>
          <td class="ts" :title="b.created_at">{{ fmtCreated(b.created_at) }}</td>
          <td class="assignee-cell">
            <button v-if="!b.assignee" class="link-btn" @click="assigningBug = b" title="Assign">+ Assign</button>
            <button v-else class="assignee-chip" @click="assigningBug = b" :title="`Assigned to ${b.assignee}`">
              👤 {{ b.assignee }}
            </button>
          </td>
          <td>
            <div class="row-actions">
              <button class="btn btn-sm" @click="editingBug = b" title="Edit">Edit</button>
              <button class="btn btn-sm" @click="duplicateBug(b)" title="Duplicate">⧉</button>
              <button class="btn btn-sm btn-danger" @click="deleteBug(b.id)" title="Delete">Del</button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <BugEditModal :bug="editingBug" :project-id="projects.current" @close="editingBug = null" @saved="loadBugs" />
  <BugAssignModal :bug="assigningBug" :project-id="projects.current" @close="assigningBug = null"
                  @saved="() => { loadBugs(); bugsStore.load() }" />
</template>

<style scoped>
.count { font-size: 12px; color: var(--muted); font-weight: 400; }

.form-grid { display: grid; grid-template-columns: 2fr 1fr 1fr auto; gap: 8px; align-items: end; max-width: 960px; }
.field label { display: block; font-size: 11px; color: var(--muted); margin-bottom: 3px; font-weight: 600; }
.field input, .field select { width: 100%; }

@media (max-width: 640px) {
  /* Add Bug: Title gets its own full-width row, then Severity + Status side-by-side, Add button full-width */
  .form-grid { grid-template-columns: 1fr 1fr; gap: 10px; }
  .form-grid > .field:first-child { grid-column: 1 / -1; }
  .form-grid > button { grid-column: 1 / -1; min-height: 44px; }
}
.form-extra { margin-top: 10px; max-width: 960px; }
.form-extra textarea {
  width: 100%;
  font-family: inherit;
  resize: vertical;
  min-height: 60px;
}

/* Filter bar */
.filter-bar {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-top: 4px;
}
.search {
  flex: 1;
  min-width: 200px;
  max-width: 320px;
  font-size: 12.5px;
}
.filter-sel { font-size: 12px; max-width: 180px; width: auto; }
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
  white-space: nowrap;
}
.seg-btn:hover { color: var(--text); }
.seg-btn.active {
  background: var(--card);
  color: var(--text);
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}

/* Stat tiles — color per severity, show open / total */
.stat-row { display: flex; gap: 12px; margin-bottom: 14px; flex-wrap: wrap; }
.stat {
  background: var(--bg);
  border: 1px solid var(--border-soft);
  border-left: 4px solid var(--border);
  border-radius: var(--radius-md);
  padding: 10px 16px;
  min-width: 130px;
}
.stat .n {
  font-size: 24px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: -0.02em;
}
.stat .n-sub { font-size: 13px; font-weight: 500; color: var(--muted); margin-left: 2px; }
.stat .l { font-size: 11px; text-transform: uppercase; color: var(--muted); letter-spacing: .3px; font-weight: 600; }
.stat .l-sub { font-size: 9.5px; font-weight: 500; opacity: 0.7; text-transform: lowercase; letter-spacing: 0; }
.stat.sev-Critical { border-left-color: var(--danger);  background: var(--danger-soft); }
.stat.sev-High     { border-left-color: #FF6B5C;        background: rgba(255, 107, 92, 0.08); }  /* stylelint-disable-line color-no-hex */
.stat.sev-Medium   { border-left-color: var(--warn);    background: var(--warn-soft); }
.stat.sev-Low      { border-left-color: var(--success); background: var(--success-soft); }
.stat.sev-Critical .n { color: var(--danger); }
.stat.sev-High .n     { color: #D04A3C; }  /* stylelint-disable-line color-no-hex */
.stat.sev-Medium .n   { color: var(--warn); }
.stat.sev-Low .n      { color: var(--success); }
[data-theme="dark"] .stat.sev-Medium .n { color: var(--warn); }
[data-theme="dark"] .stat.sev-Low .n    { color: var(--success); }

/* Table */
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 8px 10px; border-bottom: 1px solid var(--border-soft); text-align: left; vertical-align: middle; }
th { background: var(--bg); font-size: 11px; text-transform: uppercase; color: var(--muted); letter-spacing: .3px; }

.desc-icon {
  margin-left: 8px;
  font-size: 12px;
  cursor: help;
  opacity: 0.6;
}

.aging { font-weight: 600; font-size: 12px; }
.aging.age-mute { color: var(--muted); font-weight: 400; }
.aging.age-mid  { color: var(--warn); }
.aging.age-bad  { color: var(--danger); }
.ts { font-family: "SF Mono", monospace; font-size: 11.5px; color: var(--muted); cursor: help; }
.assignee-cell { font-size: 12px; color: var(--muted); }

.empty {
  text-align: center;
  padding: 40px 20px;
  color: var(--muted);
}

/* Bulk action bar — sticky just below the toolbar so user keeps context while scrolling */
.bulk-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  margin-bottom: var(--space-3);
  background: var(--primary-soft);
  border: 1px solid var(--primary);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text);
  box-shadow: var(--shadow-sm);
  position: sticky;
  top: 64px;
  z-index: 5;
}
.bulk-bar b { color: var(--primary-dk, var(--primary)); }
tr.selected { background: var(--primary-soft); }
tr.selected:hover { background: var(--primary-soft); filter: brightness(0.97); }
.empty-icon { font-size: 32px; margin-bottom: 10px; opacity: .55; }
.empty b { color: var(--text); font-weight: 600; }
.empty-hint { font-size: 12px; margin-top: 4px; }

.btn-sm { padding: 3px 9px; font-size: 11.5px; }

.link-btn {
  background: none;
  border: 1px dashed var(--border);
  border-radius: var(--radius-xs);
  padding: 2px 8px;
  font-size: 11px;
  color: var(--muted);
  cursor: pointer;
  font-family: inherit;
}
.link-btn:hover { border-color: var(--primary); color: var(--primary); }
.assignee-chip {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 2px 9px;
  font-size: 11.5px;
  color: var(--text);
  cursor: pointer;
}
.assignee-chip:hover { border-color: var(--primary); }

/* View toggle: Table / Kanban */
.view-toggle {
  display: inline-flex;
  background: var(--bg);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  padding: 3px;
  margin-bottom: var(--space-3);
}
.vt-btn {
  background: transparent;
  border: none;
  font-family: inherit;
  font-size: 12.5px;
  color: var(--muted);
  padding: 6px 14px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease);
}
.vt-btn:hover { color: var(--text); }
.vt-btn.active {
  background: var(--card);
  color: var(--text);
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}

.row-actions { display: flex; gap: 4px; }

/* Inline severity select (now editable like status, for symmetry) */
.sev-inline {
  font-size: 11px;
  font-weight: 700;
  padding: 3px 22px 3px 10px;
  border-radius: 10px;
  border: 1px solid transparent;
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><path d='M1 1l4 4 4-4' stroke='%23999' fill='none' stroke-width='1.5' stroke-linecap='round'/></svg>");
  background-repeat: no-repeat;
  background-position: right 6px center;
  transition: all var(--duration-fast) var(--ease);
}
.sev-inline.sev-Critical { background-color: var(--danger);       color: white; }
.sev-inline.sev-High     { background-color: var(--danger-soft);  color: var(--danger); }
.sev-inline.sev-Medium   { background-color: var(--warn-soft);    color: var(--warn); }
.sev-inline.sev-Low      { background-color: var(--success-soft); color: var(--success); }
[data-theme="dark"] .sev-inline.sev-Medium { color: var(--warn); }
[data-theme="dark"] .sev-inline.sev-Low    { color: var(--success); }
.sev-inline:hover { transform: translateY(-1px); box-shadow: var(--shadow-sm); }

/* Inline status select — looks like a pill, becomes a dropdown on click */
.status-inline {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 22px 3px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-soft);
  cursor: pointer;
  background: var(--card);
  color: var(--text);
  appearance: none;
  -webkit-appearance: none;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><path d='M1 1l4 4 4-4' stroke='%236E6E73' fill='none' stroke-width='1.5' stroke-linecap='round'/></svg>");
  background-repeat: no-repeat;
  background-position: right 6px center;
  transition: background-color var(--duration-fast) var(--ease);
}
.status-inline.s-Open   { background-color: var(--warn-soft); color: var(--warn); }
.status-inline.s-Fixed  { background-color: var(--success-soft); color: var(--success); }
.status-inline.s-Closed { background-color: var(--bg); color: var(--muted); }
[data-theme="dark"] .status-inline.s-Open  { color: var(--warn); }
[data-theme="dark"] .status-inline.s-Fixed { color: var(--success); }
.status-inline:hover { border-color: var(--primary); }
</style>
