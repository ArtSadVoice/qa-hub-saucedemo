<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { apiCall } from '@/api/client'
import { useProjectStore } from '@/stores/projects'
import type { Project } from '@/api/types'

interface FlakSnapshot {
  project_id?: string
  verdict: string                  // stable | warn | flaky | broken | unknown
  verdict_reason?: string
  fail_rate_pct: number
  pass_rate_tests: number | null
  runs_in_window: number
  last_status?: string
}

interface ReleaseGate {
  verdict: 'GO' | 'NOGO' | 'NOT_READY' | 'SKIP_PLANNING' | 'SKIP_PAUSED' | string
  go: boolean
  summary: { total: number; pass: number; warn: number; hard_fail: number }
}

interface RunHistEntry {
  ts: string
  pass: number
  fail: number
  rc?: number
}

interface SummaryRow {
  id: string
  total_tc?: number
  pass?: number
  fail?: number
  accuracy?: number
  has_xlsx?: boolean
  has_docx?: boolean
  last_run?: string | null
}

interface ProjectRollup {
  project: Project
  flak?: FlakSnapshot
  bugCount?: number
  releaseGate?: ReleaseGate
  history?: RunHistEntry[]    // last N runs for sparkline
  summary?: SummaryRow        // /api/summary fields — for Data view
  loading: boolean
}

interface MetricsSnapshot {
  uptime_seconds: number
  total_requests: number
  total_errors: number
  error_rate_pct: number
  rps_lifetime: number
  routes: { route: string; p95_ms: number; errors: number; count: number }[]
}

const router = useRouter()
const projectsStore = useProjectStore()

const rollups = ref<ProjectRollup[]>([])
const metrics = ref<MetricsSnapshot | null>(null)
const refreshing = ref(false)
const lastLoaded = ref<Date | null>(null)
type FilterPhase = 'all' | 'active' | 'planning' | 'paused'
type GroupBy = 'none' | 'company' | 'category'
type ViewMode = 'health' | 'data' | 'all'
type StatusFilter = 'all' | 'pass' | 'fail' | 'no-tcm'

const phaseFilter = ref<FilterPhase>('all')
const search = ref('')
const groupBy = ref<GroupBy>((localStorage.getItem('fp_overview_group') as GroupBy) || 'none')
// View mode toggle — Health (current default) shows verdict + sparkline +
// release gate; Data shows the legacy raw counts (TCs/Pass/Fail/Excel/Word/
// Last Run); All shows everything (wider table; horizontal scroll on
// narrow screens).
const viewMode = ref<ViewMode>((localStorage.getItem('fp_overview_view') as ViewMode) || 'health')
// Status filter only matters for Data view (test-result-presence based)
const statusFilter = ref<StatusFilter>('all')

// Persist user prefs so they don't have to re-select on each visit
watch(groupBy, (v) => localStorage.setItem('fp_overview_group', v))
watch(viewMode, (v) => localStorage.setItem('fp_overview_view', v))

// Column visibility — derived from viewMode; centralised so template
// stays simple and adding a column is one entry.
const cols = computed(() => ({
  // Health-only
  flakiness: viewMode.value === 'health' || viewMode.value === 'all',
  sparkline: viewMode.value === 'health' || viewMode.value === 'all',
  runFail:   viewMode.value === 'health' || viewMode.value === 'all',
  passPct:   viewMode.value === 'health' || viewMode.value === 'all',
  bugs:      viewMode.value === 'health' || viewMode.value === 'all',
  gate:      viewMode.value === 'health' || viewMode.value === 'all',
  // Data-only (legacy port)
  company:   viewMode.value === 'data'   || viewMode.value === 'all',
  category:  viewMode.value === 'data'   || viewMode.value === 'all',
  totalTc:   viewMode.value === 'data'   || viewMode.value === 'all',
  pass:      viewMode.value === 'data'   || viewMode.value === 'all',
  fail:      viewMode.value === 'data'   || viewMode.value === 'all',
  accuracy:  viewMode.value === 'data'   || viewMode.value === 'all',
  excel:     viewMode.value === 'data'   || viewMode.value === 'all',
  word:      viewMode.value === 'data'   || viewMode.value === 'all',
  lastRun:   viewMode.value === 'data'   || viewMode.value === 'all',
}))

const verdictRank = { broken: 4, flaky: 3, warn: 2, stable: 1, unknown: 0 } as Record<string, number>

// Verdicts shouldn't fire for projects that are intentionally idle.
// 'planning' = no tests yet, 'paused' = deliberately stopped → don't count
// against health KPIs even if flakiness verdict is 'unknown' or 'broken'.
function isActive(p: Project): boolean {
  return !p.phase || p.phase === 'active'
}

const filteredRollups = computed(() => {
  const q = search.value.trim().toLowerCase()
  return rollups.value.filter((r) => {
    if (phaseFilter.value !== 'all' && (r.project.phase || 'active') !== phaseFilter.value) return false
    if (q) {
      const hay = [r.project.name, r.project.id,
                   r.project.company || '', r.project.category || '']
                  .join(' ').toLowerCase()
      if (!hay.includes(q)) return false
    }
    // Status filter (only effective in Data view; ignored in Health view)
    if (viewMode.value !== 'health' && statusFilter.value !== 'all') {
      const s = r.summary
      if (statusFilter.value === 'pass'   && !(s && (s.pass || 0) > 0))      return false
      if (statusFilter.value === 'fail'   && !(s && (s.fail || 0) > 0))      return false
      if (statusFilter.value === 'no-tcm' && (s && s.has_xlsx))              return false
    }
    return true
  })
})

const sortedRollups = computed(() =>
  filteredRollups.value.slice().sort((a, b) => {
    const ra = verdictRank[a.flak?.verdict || 'unknown'] || 0
    const rb = verdictRank[b.flak?.verdict || 'unknown'] || 0
    return rb - ra
  })
)

// Group sortedRollups by the chosen taxonomy. "Other" bucket holds projects
// with no value set. Real values come first (alphabetical), "Other" last so
// the unfinished bookkeeping is visible but doesn't dominate.
interface RollupGroup { key: string; label: string; items: ProjectRollup[] }
const groupedRollups = computed<RollupGroup[]>(() => {
  if (groupBy.value === 'none') {
    return [{ key: '__all__', label: '', items: sortedRollups.value }]
  }
  const buckets = new Map<string, ProjectRollup[]>()
  for (const r of sortedRollups.value) {
    const v = (r.project[groupBy.value] || '').trim()
    const k = v || '__other__'
    if (!buckets.has(k)) buckets.set(k, [])
    buckets.get(k)!.push(r)
  }
  const entries = Array.from(buckets.entries())
  // Real values alphabetical; "Other" pinned last
  entries.sort((a, b) => {
    if (a[0] === '__other__') return 1
    if (b[0] === '__other__') return -1
    return a[0].localeCompare(b[0])
  })
  const icon = groupBy.value === 'company' ? '🏢' : '📁'
  return entries.map(([key, items]) => ({
    key,
    label: key === '__other__' ? '◌ Other (no ' + groupBy.value + ')' : `${icon} ${key}`,
    items,
  }))
})

// Summary excludes inactive projects so a paused project doesn't pollute the
// "broken / flaky" tile.
const summary = computed(() => {
  const active = rollups.value.filter((r) => isActive(r.project))
  return {
    total:          rollups.value.length,
    activeTotal:    active.length,
    broken:         active.filter((p) => p.flak?.verdict === 'broken').length,
    flaky:          active.filter((p) => p.flak?.verdict === 'flaky').length,
    warn:           active.filter((p) => p.flak?.verdict === 'warn').length,
    stable:         active.filter((p) => p.flak?.verdict === 'stable').length,
    needsAttention: active.filter((p) => p.releaseGate && p.releaseGate.verdict === 'NOGO').length,
    paused:         rollups.value.filter((r) => r.project.phase === 'paused' || r.project.phase === 'planning').length,
  }
})

async function loadProjectData(rollup: ProjectRollup) {
  const pid = rollup.project.id
  const [flak, bugs, gate, hist] = await Promise.allSettled([
    apiCall<FlakSnapshot>(`/api/flakiness?p=${pid}&window=20`, { silent: true }),
    apiCall<unknown[]>(`/api/bugs?p=${pid}`, { silent: true }),
    apiCall<ReleaseGate>(`/api/release-gate?p=${pid}`, { silent: true }),
    apiCall<RunHistEntry[]>(`/api/run/history?p=${pid}`, { silent: true }),
  ])
  if (flak.status === 'fulfilled') rollup.flak = flak.value
  if (bugs.status === 'fulfilled') rollup.bugCount = (bugs.value as unknown[])?.length || 0
  if (gate.status === 'fulfilled') rollup.releaseGate = gate.value
  if (hist.status === 'fulfilled') rollup.history = (hist.value || []).slice(-20)
  rollup.loading = false
}

// Sparkline geometry — 20 bars, each represents one test run.
// Color per bar: green = pass, red = fail (rc != 0 OR fail > 0).
const SPARK_W = 80
const SPARK_H = 22
function sparkBars(history?: RunHistEntry[]): { x: number; y: number; w: number; h: number; pass: boolean }[] {
  if (!history || !history.length) return []
  const n = history.length
  const gap = 1
  const barW = Math.max(1, (SPARK_W - gap * (n - 1)) / n)
  const totals = history.map((e) => e.pass + e.fail)
  const max = Math.max(1, ...totals)
  return history.map((e, i) => {
    const total = e.pass + e.fail || 1
    const isPass = (e.rc === 0 || e.rc === undefined) && e.fail === 0 && e.pass > 0
    // Bar height proportional to test count, min 4px so empty runs are still visible
    const h = Math.max(4, Math.round((total / max) * SPARK_H))
    return {
      x: i * (barW + gap),
      y: SPARK_H - h,
      w: barW,
      h,
      pass: isPass,
    }
  })
}

async function loadAll() {
  refreshing.value = true
  try {
    const projects = (await apiCall<Project[]>('/api/projects')) || []
    rollups.value = projects.map((p) => ({ project: p, loading: true }))
    // Fetch in parallel:
    //  - per-project health data (5 calls × N projects)
    //  - hub metrics snapshot
    //  - /api/summary — one call returns array with raw counts for ALL
    //    projects, we attach by id so Data view has TCs/Pass/Fail/etc.
    const [, metricsResult, summaryResult] = await Promise.allSettled([
      Promise.all(rollups.value.map(loadProjectData)),
      apiCall<MetricsSnapshot>('/api/metrics', { silent: true }),
      apiCall<SummaryRow[]>('/api/summary', { silent: true }),
    ])
    if (metricsResult.status === 'fulfilled') metrics.value = metricsResult.value
    if (summaryResult.status === 'fulfilled' && Array.isArray(summaryResult.value)) {
      const byId = new Map(summaryResult.value.map((s) => [s.id, s]))
      for (const r of rollups.value) {
        const s = byId.get(r.project.id)
        if (s) r.summary = s
      }
    }
    lastLoaded.value = new Date()
  } finally {
    refreshing.value = false
  }
}

// Format uptime as "1d 4h" / "23m" / "47s" — compact for a tile
function fmtUptime(secs?: number): string {
  if (!secs) return '—'
  const d = Math.floor(secs / 86400)
  if (d) return `${d}d ${Math.floor((secs % 86400) / 3600)}h`
  const h = Math.floor(secs / 3600)
  if (h) return `${h}h ${Math.floor((secs % 3600) / 60)}m`
  const m = Math.floor(secs / 60)
  if (m) return `${m}m`
  return `${secs}s`
}

// Slowest endpoint (top of routes list — backend sorts by p95 desc)
const slowestRoute = computed(() => metrics.value?.routes?.[0])

onMounted(loadAll)

function openProject(r: ProjectRollup) {
  // select() handles localStorage persistence and reactive update across views
  projectsStore.select(r.project.id)
  router.push('/dashboard')
}

// ── Badge helpers ───────────────────────────────────────────────────────────
const verdictBadge = (v?: string) => {
  switch (v) {
    case 'stable': return { cls: 'b-ok',    label: 'STABLE' }
    case 'warn':   return { cls: 'b-warn',  label: 'WARN' }
    case 'flaky':  return { cls: 'b-fail',  label: 'FLAKY' }
    case 'broken': return { cls: 'b-crit',  label: 'BROKEN' }
    default:       return { cls: 'b-mute',  label: 'UNKNOWN' }
  }
}

// Release-gate verdict has 5 distinct meanings — collapsing to bool loses
// the difference between "not started yet" and "real failure".
const gateBadge = (g?: ReleaseGate) => {
  if (!g) return { cls: 'b-mute', label: '—', tip: '' }
  switch (g.verdict) {
    case 'GO':            return { cls: 'b-ok',    label: 'GO',        tip: 'All gates passed' }
    case 'NOGO':          return { cls: 'b-fail',  label: g.summary.hard_fail ? `${g.summary.hard_fail} hard fail` : 'NOGO',
                                   tip: `${g.summary.hard_fail} hard fail · ${g.summary.warn} warn` }
    case 'NOT_READY':     return { cls: 'b-warn',  label: 'NOT READY', tip: 'No tests run yet' }
    case 'SKIP_PLANNING': return { cls: 'b-mute',  label: 'PLANNING',  tip: 'Project in planning phase' }
    case 'SKIP_PAUSED':   return { cls: 'b-mute',  label: 'PAUSED',    tip: 'Project paused' }
    default:              return { cls: 'b-mute',  label: g.verdict,   tip: '' }
  }
}

const failRateClass = (pct?: number) => {
  if (pct === undefined) return ''
  if (pct > 20) return 'rate-bad'
  if (pct > 5)  return 'rate-mid'
  return 'rate-good'
}

const fmtTime = (d: Date | null) =>
  d ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : ''
</script>

<template>
  <!-- Top-line summary stats -->
  <div class="card">
    <div class="card-title" style="display:flex;align-items:center;gap:8px">
      🌐 All Projects Overview
      <span v-if="lastLoaded" class="ts">· refreshed {{ fmtTime(lastLoaded) }}</span>
      <button class="btn btn-sm" :disabled="refreshing" @click="loadAll" style="margin-left:auto">
        {{ refreshing ? '⏳' : '↻' }} Refresh
      </button>
    </div>
    <p class="sub">Cross-project rollup — flakiness, open bugs, release gate. Click a row → open that project.</p>
    <div class="stat-row">
      <div class="stat">
        <div class="n">{{ summary.activeTotal }}<span v-if="summary.paused" class="muted">/{{ summary.total }}</span></div>
        <div class="l">Active project{{ summary.activeTotal === 1 ? '' : 's' }}</div>
      </div>
      <div class="stat danger" v-if="summary.broken || summary.flaky">
        <div class="n">{{ summary.broken + summary.flaky }}</div>
        <div class="l">broken / flaky</div>
      </div>
      <div class="stat warn" v-if="summary.warn">
        <div class="n">{{ summary.warn }}</div>
        <div class="l">warn band</div>
      </div>
      <div class="stat ok" v-if="summary.stable">
        <div class="n">{{ summary.stable }}</div>
        <div class="l">stable</div>
      </div>
      <div class="stat danger" v-if="summary.needsAttention">
        <div class="n">{{ summary.needsAttention }}</div>
        <div class="l">gate NOGO</div>
      </div>
      <div class="stat muted" v-if="summary.paused">
        <div class="n">{{ summary.paused }}</div>
        <div class="l">paused/planning</div>
      </div>
    </div>

    <!-- Hub runtime metrics — separate strip so the project KPIs stay visually grouped -->
    <div v-if="metrics" class="metrics-strip" title="Source: /api/metrics — resets on Hub restart">
      <div class="metric-tile">
        <span class="m-label">Uptime</span>
        <span class="m-val">{{ fmtUptime(metrics.uptime_seconds) }}</span>
      </div>
      <div class="metric-tile">
        <span class="m-label">Requests</span>
        <span class="m-val">{{ metrics.total_requests.toLocaleString() }}</span>
      </div>
      <div class="metric-tile" :class="{ alert: metrics.error_rate_pct > 1 }">
        <span class="m-label">Error rate</span>
        <span class="m-val">{{ metrics.error_rate_pct }}%</span>
        <span class="m-sub" v-if="metrics.total_errors">{{ metrics.total_errors }} 5xx</span>
      </div>
      <div class="metric-tile" v-if="slowestRoute">
        <span class="m-label">Slowest p95</span>
        <span class="m-val">{{ slowestRoute.p95_ms }}<small>ms</small></span>
        <code class="m-sub" :title="slowestRoute.route">{{ slowestRoute.route }}</code>
      </div>
    </div>
  </div>

  <!-- Per-project table -->
  <div class="card">
    <div class="card-title" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
      Project Health Matrix
      <div class="seg" role="group" aria-label="View mode" title="Switch column set: Health vs Data vs All">
        <span class="seg-prefix">View:</span>
        <button class="seg-btn" :class="{ active: viewMode === 'health' }" @click="viewMode = 'health'" title="Flakiness, sparkline, bugs, release gate">🏥 Health</button>
        <button class="seg-btn" :class="{ active: viewMode === 'data' }" @click="viewMode = 'data'" title="TCs, pass/fail counts, artifact presence, last run">📊 Data</button>
        <button class="seg-btn" :class="{ active: viewMode === 'all' }" @click="viewMode = 'all'" title="Show everything (wide table)">🔀 All</button>
      </div>
      <input v-model="search" type="text" placeholder="Search project…" class="search" />
      <div class="seg" role="group" aria-label="Phase filter">
        <button class="seg-btn" :class="{ active: phaseFilter === 'all' }" @click="phaseFilter = 'all'">All</button>
        <button class="seg-btn" :class="{ active: phaseFilter === 'active' }" @click="phaseFilter = 'active'">Active</button>
        <button class="seg-btn" :class="{ active: phaseFilter === 'planning' }" @click="phaseFilter = 'planning'">Planning</button>
        <button class="seg-btn" :class="{ active: phaseFilter === 'paused' }" @click="phaseFilter = 'paused'">Paused</button>
      </div>
      <div v-if="viewMode !== 'health'" class="seg" role="group" aria-label="Status filter" title="Filter by test result presence">
        <span class="seg-prefix">Status:</span>
        <button class="seg-btn" :class="{ active: statusFilter === 'all' }" @click="statusFilter = 'all'">All</button>
        <button class="seg-btn" :class="{ active: statusFilter === 'pass' }" @click="statusFilter = 'pass'">✅ Has Pass</button>
        <button class="seg-btn" :class="{ active: statusFilter === 'fail' }" @click="statusFilter = 'fail'">❌ Has Fail</button>
        <button class="seg-btn" :class="{ active: statusFilter === 'no-tcm' }" @click="statusFilter = 'no-tcm'">📭 No TCM</button>
      </div>
      <div class="seg" role="group" aria-label="Group by" title="Group rows by Company or Category">
        <span class="seg-prefix">Group:</span>
        <button class="seg-btn" :class="{ active: groupBy === 'none' }" @click="groupBy = 'none'">None</button>
        <button class="seg-btn" :class="{ active: groupBy === 'company' }" @click="groupBy = 'company'">🏢 Company</button>
        <button class="seg-btn" :class="{ active: groupBy === 'category' }" @click="groupBy = 'category'">📁 Category</button>
      </div>
    </div>

    <!-- Skeleton while initial fetch is in flight -->
    <table v-if="refreshing && !rollups.length">
      <thead>
        <tr>
          <th>Project</th><th>Type</th><th>Flakiness</th><th>Last 20</th>
          <th style="text-align:right">Run fail %</th>
          <th style="text-align:right">Test pass %</th>
          <th style="text-align:right">Open bugs</th>
          <th>Release gate</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="i in 4" :key="i" class="skeleton-row">
          <td colspan="8"><div class="skeleton-bar"></div></td>
        </tr>
      </tbody>
    </table>

    <!-- Empty: no projects configured -->
    <div v-else-if="!rollups.length" class="empty">
      <div class="empty-icon">📭</div>
      <div><b>ยังไม่มี project</b></div>
      <div class="empty-hint">เพิ่ม project ใน <router-link to="/projects">Projects tab</router-link> เพื่อเริ่มดู rollup</div>
    </div>

    <!-- Empty: filter excluded everything -->
    <div v-else-if="!sortedRollups.length" class="empty">
      <div class="empty-icon">🔍</div>
      <div>ไม่พบ project ที่ตรงกับ filter</div>
      <button class="btn btn-sm" @click="search = ''; phaseFilter = 'all'" style="margin-top:10px">Clear filters</button>
    </div>

    <template v-else>
      <div v-for="g in groupedRollups" :key="g.key" class="group-block" :class="{ 'is-other': g.key === '__other__' }">
        <div v-if="g.label" class="group-head">
          <span class="group-name">{{ g.label }}</span>
          <span class="group-count">{{ g.items.length }} project{{ g.items.length === 1 ? '' : 's' }}</span>
        </div>
        <table>
          <thead v-if="g.key === '__all__' || groupedRollups[0].key === g.key">
            <tr>
              <th>Project</th>
              <th style="width:90px">Type</th>
              <th v-if="cols.company" style="width:120px">Company</th>
              <th v-if="cols.category" style="width:110px">Category</th>
              <th v-if="cols.totalTc" style="width:60px;text-align:right">TCs</th>
              <th v-if="cols.pass" style="width:60px;text-align:right">Pass</th>
              <th v-if="cols.fail" style="width:60px;text-align:right">Fail</th>
              <th v-if="cols.accuracy" style="width:80px;text-align:right">Pass rate</th>
              <th v-if="cols.flakiness" style="width:90px">Flakiness</th>
              <th v-if="cols.sparkline" style="width:90px">Last 20</th>
              <th v-if="cols.runFail" style="width:80px;text-align:right">Run fail %</th>
              <th v-if="cols.passPct" style="width:80px;text-align:right">Test pass %</th>
              <th v-if="cols.bugs" style="width:80px;text-align:right">Open bugs</th>
              <th v-if="cols.gate" style="width:120px">Release gate</th>
              <th v-if="cols.excel" style="width:55px;text-align:center">Excel</th>
              <th v-if="cols.word" style="width:55px;text-align:center">Word</th>
              <th v-if="cols.lastRun" style="width:120px">Last Run</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in g.items" :key="r.project.id"
                class="prj-row" :class="{ inactive: !isActive(r.project) }"
                @click="openProject(r)">
              <td>
                <span v-if="r.project.color" class="color-dot" :style="{ background: r.project.color }"></span>
                <b>{{ r.project.name }}</b>
                <span v-if="r.project.phase && r.project.phase !== 'active'" class="phase-tag">{{ r.project.phase }}</span>
                <span v-if="r.project.exists === false" class="missing-flag" title="Folder not found">⚠</span>
              </td>
              <td class="muted">{{ r.project.type }}</td>
              <td v-if="cols.company" class="muted">{{ r.project.company || '—' }}</td>
              <td v-if="cols.category" class="muted">{{ r.project.category || '—' }}</td>
              <td v-if="cols.totalTc" class="num">{{ r.summary?.total_tc || '—' }}</td>
              <td v-if="cols.pass" class="num" :class="{ 'rate-good': (r.summary?.pass || 0) > 0 }">{{ r.summary?.pass || '—' }}</td>
              <td v-if="cols.fail" class="num" :class="{ 'rate-bad': (r.summary?.fail || 0) > 0 }">{{ r.summary?.fail || '—' }}</td>
              <td v-if="cols.accuracy" class="num">
                <template v-if="r.summary?.accuracy != null">{{ r.summary.accuracy }}%</template>
                <span v-else class="muted">—</span>
              </td>
              <td v-if="cols.flakiness">
                <span v-if="r.flak" class="badge" :class="verdictBadge(r.flak.verdict).cls"
                      :title="r.flak.verdict_reason || ''">
                  {{ verdictBadge(r.flak.verdict).label }}
                </span>
                <span v-else-if="r.loading" class="loading-dot">…</span>
                <span v-else class="muted small">no data</span>
              </td>
              <td v-if="cols.sparkline">
                <svg v-if="r.history && r.history.length" :width="SPARK_W" :height="SPARK_H"
                     class="spark" :title="`${r.history.length} runs · ${r.history.filter(h => h.fail === 0 && (h.rc === 0 || h.rc === undefined)).length} pass / ${r.history.filter(h => h.fail > 0 || (h.rc !== undefined && h.rc !== 0)).length} fail`">
                  <rect v-for="(b, bi) in sparkBars(r.history)" :key="bi"
                        :x="b.x" :y="b.y" :width="b.w" :height="b.h"
                        :class="b.pass ? 's-pass' : 's-fail'" />
                </svg>
                <span v-else-if="r.loading" class="loading-dot">…</span>
                <span v-else class="muted small">—</span>
              </td>
              <td v-if="cols.runFail" class="num" :class="failRateClass(r.flak?.fail_rate_pct)">
                <template v-if="r.flak">{{ r.flak.fail_rate_pct }}%</template>
                <span v-else class="muted">—</span>
              </td>
              <td v-if="cols.passPct" class="num">
                <template v-if="r.flak?.pass_rate_tests !== null && r.flak?.pass_rate_tests !== undefined">
                  {{ r.flak.pass_rate_tests }}%
                </template>
                <span v-else class="muted">—</span>
              </td>
              <td v-if="cols.bugs" class="num" :class="{ 'rate-bad': (r.bugCount || 0) > 0 }">
                {{ r.bugCount ?? '—' }}
              </td>
              <td v-if="cols.gate">
                <span v-if="r.releaseGate" class="badge" :class="gateBadge(r.releaseGate).cls"
                      :title="gateBadge(r.releaseGate).tip">
                  {{ gateBadge(r.releaseGate).label }}
                </span>
                <span v-else-if="r.loading" class="loading-dot">…</span>
                <span v-else class="muted small">—</span>
              </td>
              <td v-if="cols.excel" style="text-align:center">
                <span v-if="r.summary?.has_xlsx" class="rate-good" title="TCM Excel present">✓</span>
                <span v-else class="muted">—</span>
              </td>
              <td v-if="cols.word" style="text-align:center">
                <span v-if="r.summary?.has_docx" class="rate-good" title="Report docx present">✓</span>
                <span v-else class="muted">—</span>
              </td>
              <td v-if="cols.lastRun" class="muted small ts">
                {{ r.summary?.last_run || '—' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<style scoped>
.sub { color: var(--muted); font-size: 13px; margin-bottom: 12px; }
.ts { color: var(--muted); font-size: 11.5px; font-weight: 400; }
.muted { color: var(--muted); }
.muted.small { font-size: 11px; }

/* Search + segmented control on table header */
.search {
  font-size: 12.5px;
  min-width: 180px;
  max-width: 240px;
  margin-left: auto;
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
.seg-prefix {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  color: var(--muted);
  font-weight: 600;
  padding: 4px 6px 4px 8px;
  align-self: center;
}

/* Group blocks (Company / Category) */
.group-block + .group-block { margin-top: var(--space-3); }
.group-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 8px 4px 6px;
  border-bottom: 1px solid var(--border-soft);
  margin-bottom: 4px;
}
.group-name {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: -0.01em;
}
.group-count {
  font-size: 11px;
  color: var(--muted);
  font-weight: 500;
}
.group-block.is-other .group-name { color: var(--muted); font-style: italic; }

/* Hub runtime metrics strip (separate from project KPIs) */
.metrics-strip {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
  padding: 10px 12px;
  background: var(--bg);
  border: 1px dashed var(--border-soft);
  border-radius: var(--radius-md);
}
.metric-tile {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 4px 12px;
  border-right: 1px solid var(--border-soft);
  min-width: 110px;
}
.metric-tile:last-child { border-right: none; }
.metric-tile.alert .m-val { color: var(--danger); }
.m-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  color: var(--muted);
  font-weight: 600;
}
.m-val {
  font-size: 16px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: -0.01em;
  font-family: "SF Mono", monospace;
}
.m-val small { font-size: 10px; font-weight: 500; color: var(--muted); margin-left: 1px; }
.m-sub {
  font-size: 10.5px;
  color: var(--muted);
  font-family: "SF Mono", monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}
.metric-tile.alert .m-sub { color: var(--danger); }

/* Stat tiles */
.stat-row { display: flex; gap: 12px; flex-wrap: wrap; }
.stat {
  background: var(--bg);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  padding: 10px 16px;
  min-width: 110px;
  text-align: center;
}
.stat .n { font-size: 26px; font-weight: 700; color: var(--text); letter-spacing: -0.02em; }
.stat .n .muted { font-size: 14px; font-weight: 500; color: var(--muted); }
.stat .l { font-size: 11px; text-transform: uppercase; color: var(--muted); letter-spacing: .5px; }
.stat.ok     { background: var(--success-soft); }
.stat.warn   { background: var(--warn-soft); }
.stat.danger { background: var(--danger-soft); }
.stat.danger .n { color: var(--danger); }
.stat.warn .n   { color: var(--warn); }
[data-theme="dark"] .stat.warn .n { color: var(--warn); }
.stat.ok .n     { color: var(--success); }
[data-theme="dark"] .stat.ok .n { color: var(--success); }

/* Table */
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 8px 10px; border-bottom: 1px solid var(--border-soft); text-align: left; vertical-align: middle; }
th { background: var(--bg); font-size: 11px; text-transform: uppercase; color: var(--muted); letter-spacing: .3px; }
.num { text-align: right; font-family: "SF Mono", monospace; font-size: 12px; }
.rate-good { color: var(--success); }
.rate-mid  { color: var(--warn); }
.rate-bad  { color: var(--danger); }

.prj-row { cursor: pointer; transition: background var(--duration-fast) var(--ease); }
.prj-row:hover { background: var(--primary-soft); }
.prj-row.inactive { opacity: 0.65; }

.phase-tag {
  display: inline-block;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  background: var(--bg);
  border: 1px solid var(--border-soft);
  color: var(--muted);
  padding: 1px 6px;
  border-radius: var(--radius-md);
  margin-left: 8px;
  letter-spacing: .3px;
}

.badge {
  display: inline-block;
  font-size: 10.5px;
  font-weight: 700;
  padding: 3px 9px;
  border-radius: 10px;
  letter-spacing: .3px;
  white-space: nowrap;
}
.b-ok   { background: var(--success-soft); color: var(--success); }
.b-warn { background: var(--warn-soft);    color: var(--warn); }
.b-fail { background: var(--danger-soft);  color: var(--danger); }
.b-crit { background: var(--danger);       color: white; }
.b-mute { background: var(--bg);           color: var(--muted); border: 1px solid var(--border-soft); }
[data-theme="dark"] .b-ok   { color: var(--success); }
[data-theme="dark"] .b-warn { color: var(--warn); }

.loading-dot {
  font-size: 16px;
  color: var(--muted);
  animation: pulse 1.4s ease-in-out infinite;
}

/* Sparkline: 20-bar mini chart for last test runs (B1) */
.spark {
  display: block;
  cursor: help;
}
.spark .s-pass { fill: var(--success); }
.spark .s-fail { fill: var(--danger); }
.spark rect    { transition: opacity var(--duration-fast) var(--ease); }
.spark:hover rect { opacity: 0.85; }
@keyframes pulse { 0%, 100% { opacity: .35; } 50% { opacity: 1; } }

/* Skeleton loader */
.skeleton-row td { padding: 14px 10px; }
.skeleton-bar {
  height: 14px;
  background: linear-gradient(90deg, var(--bg) 25%, var(--border-soft) 50%, var(--bg) 75%);
  background-size: 200% 100%;
  border-radius: var(--radius-sm);
  animation: shimmer 1.4s linear infinite;
}
@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.color-dot {
  display: inline-block;
  width: 10px; height: 10px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}
.missing-flag {
  margin-left: 6px;
  color: var(--danger);
  font-size: 12px;
  cursor: help;
}
.empty { text-align: center; padding: 40px 20px; color: var(--muted); }
.empty-icon { font-size: 36px; margin-bottom: 10px; opacity: .55; }
.empty b { color: var(--text); font-weight: 600; }
.empty-hint { font-size: 12.5px; margin-top: 6px; }
.empty-hint a { color: var(--primary); }
</style>
