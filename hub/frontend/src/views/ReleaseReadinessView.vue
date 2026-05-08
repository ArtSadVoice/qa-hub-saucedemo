<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { apiCall } from '@/api/client'
import { useProjectStore } from '@/stores/projects'
import { useToast } from '@/composables/useToast'

interface Criterion {
  id: string
  label: string
  ok: boolean
  warn: boolean
  detail: string
}

interface ReleaseGate {
  project_id: string
  project_type: string
  phase: string
  verdict: 'GO' | 'NOGO' | 'NOT_READY' | 'SKIP_PLANNING' | 'SKIP_PAUSED'
  go: boolean
  criteria: Criterion[]
  summary: { total: number; pass: number; warn: number; hard_fail: number }
  thresholds?: Record<string, number>
  reason?: string
}

const router = useRouter()
const projects = useProjectStore()
const toast = useToast()

const gate = ref<ReleaseGate | null>(null)
const initialLoading = ref(false)   // first paint blocks
const reEvaluating = ref(false)     // background refresh dims criteria only

async function load(initial = false) {
  if (!projects.current) return
  if (initial) initialLoading.value = true
  else reEvaluating.value = true
  try {
    gate.value = await apiCall<ReleaseGate>(`/api/release-gate?p=${projects.current}`)
  } finally {
    initialLoading.value = false
    reEvaluating.value = false
  }
}

// Command Palette / deep-link: ?action=reload triggers a re-evaluation
const route = useRoute()
function applyQueryAction() {
  if (route.query.action === 'reload') load(false)
}

onMounted(async () => {
  if (!projects.all.length) await projects.load()
  load(true)
  applyQueryAction()
})
watch(() => projects.current, () => load(true))
watch(() => route.query, applyQueryAction)

// ── Verdict-driven CTAs ────────────────────────────────────────────────
const verdictDisplay = computed(() => {
  const v = gate.value?.verdict
  switch (v) {
    case 'GO':            return { cls: 'v-go',   icon: '✅', title: 'GO',         hint: 'พร้อม release ได้' }
    case 'NOGO':          return { cls: 'v-fail', icon: '❌', title: 'NOGO',       hint: 'มี hard-fail criterion' }
    case 'NOT_READY':     return { cls: 'v-warn', icon: '⏳', title: 'NOT READY',  hint: 'ยังไม่มี run history — รัน tests ก่อน' }
    case 'SKIP_PLANNING': return { cls: 'v-mute', icon: '📝', title: 'PLANNING',   hint: 'project อยู่ใน planning phase' }
    case 'SKIP_PAUSED':   return { cls: 'v-mute', icon: '⏸️', title: 'PAUSED',     hint: 'project ถูก pause ไว้' }
    default:              return { cls: 'v-mute', icon: '—',  title: 'UNKNOWN',    hint: '' }
  }
})

// ── Map each criterion id to an actionable shortcut ──────────────────
interface ActionRoute { label: string; route: string; query?: Record<string, string> }
const actionFor: Record<string, ActionRoute> = {
  tcm_uploaded:      { label: 'Open Input',   route: '/input' },
  spec_complete:     { label: 'Run Stage 4',  route: '/pipeline' },
  no_not_start:      { label: 'Update TCM',   route: '/input' },
  run_scope:         { label: 'Run Stage 5',  route: '/pipeline' },
  pass_rate:         { label: 'Re-run tests', route: '/pipeline' },
  tcm_pass_rate:     { label: 'Update TCM',   route: '/input' },
  shot_coverage:     { label: 'Run Stage 5',  route: '/pipeline' },
  has_screenshots:   { label: 'Run Stage 5',  route: '/pipeline' },
  no_critical_bug:   { label: 'Open Bugs',    route: '/bugs' },
  no_high_bug:       { label: 'Open Bugs',    route: '/bugs' },
  word_report_ready: { label: 'Run Stage 7',  route: '/pipeline' },
  pw_report_ready:   { label: 'Run Stage 5',  route: '/pipeline' },
}

function gotoAction(c: Criterion) {
  const action = actionFor[c.id]
  if (!action) return
  router.push({ path: action.route, query: action.query })
}

function jumpToFirstFailure() {
  const c = gate.value?.criteria.find((x) => !x.ok && !x.warn)
  if (c) gotoAction(c)
}

function gotoSendReport() {
  router.push({ path: '/pipeline', query: { action: 'send-report' } })
}

// ── Threshold panel: overlay current value next to each threshold ─────
interface ThresholdRow { key: string; threshold: number; current: number | null; label: string }

// Mapping threshold keys ↔ criteria ids that produce comparable %s.
const thresholdSourceCriterion: Record<string, string> = {
  pass_rate:           'pass_rate',
  tcm_pass_rate:       'tcm_pass_rate',
  screenshot_coverage: 'shot_coverage',
}

const thresholdRows = computed<ThresholdRow[]>(() => {
  const t = gate.value?.thresholds
  if (!t) return []
  return Object.entries(t).map(([key, threshold]) => {
    const cid = thresholdSourceCriterion[key]
    const c   = gate.value?.criteria.find((x) => x.id === cid)
    let current: number | null = null
    if (c) {
      // Detail strings include a % token — extract the first number followed by %
      const m = c.detail.match(/(\d+(?:\.\d+)?)\s*%/)
      if (m) current = parseFloat(m[1])
    }
    return { key, threshold, current, label: key.replace(/_/g, ' ') }
  })
})

// ── A2 Sprint I — AI release summary ────────────────────────────────
const aiSummary = ref<string>('')
const aiLoading = ref(false)
const aiProvider = ref<string>('')

async function generateAiSummary() {
  if (!projects.current) return
  aiLoading.value = true
  aiSummary.value = ''
  try {
    const r = await apiCall<{ provider: string; model: string; output: string }>(
      '/api/ai/release-summary',
      { silent: true, body: { project_id: projects.current } }
    )
    aiSummary.value = r.output
    aiProvider.value = `${r.provider}${r.model && r.model !== 'default' ? ' (' + r.model + ')' : ''}`
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : 'failed'
    toast.show(`AI summary failed: ${msg}`, 'err')
  } finally {
    aiLoading.value = false
  }
}

async function copyAiSummary() {
  if (!aiSummary.value) return
  try {
    await navigator.clipboard.writeText(aiSummary.value)
    toast.show('📋 Copied AI summary', 'ok')
  } catch {
    toast.show('Copy failed', 'err')
  }
}

// ── Copy summary as markdown for release notes ──────────────────────
async function copySummary() {
  if (!gate.value) return
  const g = gate.value
  const lines: string[] = []
  lines.push(`## Release Gate — ${g.project_id}`)
  lines.push(`**Verdict:** ${g.verdict}${g.reason ? ` (${g.reason})` : ''}`)
  lines.push(`**Type:** ${g.project_type} · **Phase:** ${g.phase}`)
  lines.push(`**Summary:** ${g.summary.pass}/${g.summary.total} pass · ${g.summary.warn} warn · ${g.summary.hard_fail} hard-fail`)
  if (g.criteria.length) {
    lines.push('', '| Status | Criterion | Detail |', '| --- | --- | --- |')
    for (const c of g.criteria) {
      const icon = c.ok ? '✅' : (c.warn ? '⚠️' : '❌')
      lines.push(`| ${icon} | ${c.label} | ${c.detail} |`)
    }
  }
  try {
    await navigator.clipboard.writeText(lines.join('\n'))
    toast.show('📋 Copied release-gate summary as Markdown', 'ok')
  } catch {
    toast.show('Copy failed — clipboard API blocked', 'err')
  }
}
</script>

<template>
  <div v-if="initialLoading" class="card empty">Loading release gate…</div>

  <div v-else-if="!gate" class="card empty">
    <div class="empty-icon">🚦</div>
    <div><b>เลือก project ก่อน</b></div>
    <div class="empty-hint">Pick a project from the topbar to evaluate its release gate</div>
  </div>

  <template v-else>
    <!-- Project meta header -->
    <div class="meta-header">
      <span class="meta-name">{{ projects.currentMeta?.name || gate.project_id }}</span>
      <span class="meta-pill">{{ gate.project_type }}</span>
      <span v-if="gate.phase !== 'active'" class="meta-pill dim">{{ gate.phase }}</span>
      <button class="btn btn-sm" @click="copySummary" title="Copy as Markdown">📋 Copy</button>
      <button class="btn btn-sm" :disabled="reEvaluating" @click="load(false)">
        {{ reEvaluating ? '⏳' : '↻' }} Re-evaluate
      </button>
    </div>

    <!-- Verdict banner -->
    <div class="card verdict-banner" :class="verdictDisplay.cls">
      <div class="vb-left">
        <div class="vb-icon">{{ verdictDisplay.icon }}</div>
        <div>
          <div class="vb-title">{{ verdictDisplay.title }}</div>
          <div class="vb-hint">{{ gate.reason || verdictDisplay.hint }}</div>
        </div>
      </div>
      <div class="vb-right">
        <div class="vb-summary">
          <span><b>{{ gate.summary.pass }}</b>/{{ gate.summary.total }} pass</span>
          <span v-if="gate.summary.warn"><b>{{ gate.summary.warn }}</b> warn</span>
          <span v-if="gate.summary.hard_fail"><b>{{ gate.summary.hard_fail }}</b> hard-fail</span>
        </div>
        <div class="vb-actions">
          <button v-if="gate.verdict === 'GO'" class="btn btn-primary btn-sm" @click="gotoSendReport">
            📤 Send Report
          </button>
          <button v-else-if="gate.verdict === 'NOGO'" class="btn btn-warn btn-sm" @click="jumpToFirstFailure">
            ▶ Fix first issue
          </button>
          <button v-else-if="gate.verdict === 'NOT_READY'" class="btn btn-primary btn-sm" @click="router.push('/pipeline')">
            ▶ Run tests
          </button>
        </div>
      </div>
    </div>

    <!-- AI release summary (Sprint I A2) -->
    <div class="card ai-summary">
      <div class="card-title" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
        🤖 AI release summary
        <span class="ai-hint">— สำหรับ briefing stakeholder ที่ไม่ใช่ technical</span>
        <div style="margin-left:auto;display:flex;gap:6px">
          <button v-if="aiSummary" class="btn btn-sm" @click="copyAiSummary" title="Copy summary">📋 Copy</button>
          <button class="btn btn-sm btn-primary" :disabled="aiLoading" @click="generateAiSummary">
            {{ aiLoading ? '⏳ Generating…' : (aiSummary ? '↻ Regenerate' : '✨ Generate') }}
          </button>
        </div>
      </div>
      <p v-if="!aiSummary && !aiLoading" class="ai-empty">
        ส่ง verdict + criteria + bug counts + pass rate ไปให้ Claude สรุปเป็น 4-6 ประโยคภาษาไทย —
        ใช้แปะ Slack / chat / release notes ตอน brief ทีม.
      </p>
      <div v-if="aiSummary" class="ai-output">
        {{ aiSummary }}
        <div v-if="aiProvider" class="ai-provider">via {{ aiProvider }}</div>
      </div>
    </div>

    <!-- Criteria list -->
    <div v-if="gate.criteria.length" class="card" :class="{ dim: reEvaluating }">
      <div class="card-title">Criteria ({{ gate.summary.total }})</div>
      <div class="criteria">
        <div v-for="c in gate.criteria" :key="c.id" class="criterion"
             :class="{ pass: c.ok, warn: c.warn && !c.ok, fail: !c.ok && !c.warn }">
          <div class="ico">
            <template v-if="c.ok">✅</template>
            <template v-else-if="c.warn">⚠️</template>
            <template v-else>❌</template>
          </div>
          <div class="body">
            <div class="label">{{ c.label }}</div>
            <div class="detail">{{ c.detail }}</div>
          </div>
          <button v-if="!c.ok && actionFor[c.id]"
                  class="action-btn"
                  @click="gotoAction(c)"
                  :title="`Go to ${actionFor[c.id].route}`">
            {{ actionFor[c.id].label }} →
          </button>
        </div>
      </div>
    </div>

    <!-- Thresholds -->
    <div v-if="thresholdRows.length" class="card">
      <div class="card-title">Active thresholds</div>
      <div class="thresholds">
        <div v-for="row in thresholdRows" :key="row.key" class="th-stat"
             :class="{ 'th-pass': row.current !== null && row.current >= row.threshold,
                       'th-fail': row.current !== null && row.current < row.threshold }">
          <div class="th-row">
            <span class="th-current" v-if="row.current !== null">{{ row.current }}%</span>
            <span class="th-current th-na" v-else>—</span>
            <span class="th-sep">/</span>
            <span class="th-target">{{ row.threshold }}%</span>
          </div>
          <div class="th-label">{{ row.label }}</div>
        </div>
      </div>
      <p class="th-foot">
        Override per-project ใน <code>config.json</code> field <code>gates</code>
      </p>
    </div>
  </template>
</template>

<style scoped>
/* Empty state */
.empty {
  text-align: center;
  padding: 50px 24px;
  color: var(--muted);
}
.empty-icon { font-size: 36px; margin-bottom: 10px; opacity: .55; }
.empty b { color: var(--text); font-weight: 600; }
.empty-hint { font-size: 12.5px; margin-top: 6px; }

/* Project meta header */
.meta-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: var(--space-3);
  padding: 0 4px;
  flex-wrap: wrap;
}
.meta-name { font-size: 16px; font-weight: 700; color: var(--text); letter-spacing: -0.01em; }
.meta-pill {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 9px;
  border-radius: var(--radius-md);
  background: var(--primary-soft);
  color: var(--primary-dk, var(--primary));
  text-transform: uppercase;
  letter-spacing: .3px;
}
.meta-pill.dim { background: var(--bg); color: var(--muted); border: 1px solid var(--border-soft); }
.meta-header .btn-sm { margin-left: auto; }
.meta-header .btn-sm + .btn-sm { margin-left: 0; }

/* Verdict banner */
.verdict-banner {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: 18px 22px;
  border: 1px solid;
  border-left-width: 5px;
  border-radius: var(--radius-md);
  flex-wrap: wrap;
}
.vb-left { display: flex; gap: 14px; align-items: center; flex: 1; min-width: 240px; }
.vb-icon { font-size: 30px; }
.vb-title { font-size: 20px; font-weight: 700; letter-spacing: -0.02em; }
.vb-hint  { font-size: 13px; opacity: .8; margin-top: 2px; }
.vb-right { display: flex; flex-direction: column; gap: 6px; align-items: flex-end; }
.vb-summary { display: flex; gap: 14px; font-size: 13px; }
.vb-summary b { font-size: 14.5px; }
.vb-actions { display: flex; gap: 6px; }

.verdict-banner.v-go   { background: var(--success-soft); color: var(--success); border-color: var(--success); }
.verdict-banner.v-fail { background: var(--danger-soft);  color: var(--danger); border-color: var(--danger); }
.verdict-banner.v-warn { background: var(--warn-soft);    color: var(--warn); border-color: var(--warn); }
.verdict-banner.v-mute { background: var(--bg);           color: var(--muted); border-color: var(--border-soft); }
[data-theme="dark"] .verdict-banner.v-go   { color: var(--success); }
[data-theme="dark"] .verdict-banner.v-warn { color: var(--warn); }

/* Criteria */
.card.dim { opacity: 0.55; transition: opacity var(--duration-fast) var(--ease); }
.criteria { display: flex; flex-direction: column; gap: 6px; }
.criterion {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-soft);
  background: var(--card);
}
.criterion.pass { background: var(--success-soft); border-color: rgba(48, 209, 88, 0.3); }
.criterion.warn { background: var(--warn-soft);    border-color: rgba(255, 159, 10, 0.3); }
.criterion.fail { background: var(--danger-soft);  border-color: rgba(255, 69, 58, 0.3); }
.criterion .ico { font-size: 18px; flex-shrink: 0; }
.criterion .body { flex: 1; min-width: 0; }
.criterion .label { font-size: 13px; font-weight: 700; color: var(--text); }
.criterion .detail { font-size: 12px; color: var(--text-secondary, var(--muted)); margin-top: 2px; line-height: 1.4; }

.action-btn {
  background: var(--card);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  padding: 5px 12px;
  font: inherit;
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text);
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: all var(--duration-fast) var(--ease);
}
.action-btn:hover {
  background: var(--primary);
  color: white;
  border-color: var(--primary);
  transform: translateX(2px);
}

/* Thresholds */
.thresholds { display: flex; gap: 10px; flex-wrap: wrap; }
.th-stat {
  background: var(--bg);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  padding: 10px 16px;
  min-width: 140px;
}
.th-stat.th-pass { border-color: rgba(48, 209, 88, 0.4); background: var(--success-soft); }
.th-stat.th-fail { border-color: rgba(255, 69, 58, 0.4); background: var(--danger-soft); }
.th-row {
  font-size: 22px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: -0.02em;
  display: flex;
  align-items: baseline;
  gap: 4px;
}
.th-current { color: var(--text); }
.th-stat.th-pass .th-current { color: var(--success); }
.th-stat.th-fail .th-current { color: var(--danger); }
[data-theme="dark"] .th-stat.th-pass .th-current { color: var(--success); }
.th-current.th-na { color: var(--muted); font-weight: 500; }
.th-sep    { color: var(--muted); font-size: 16px; font-weight: 400; }
.th-target { color: var(--muted); font-size: 14px; font-weight: 500; }
.th-label  { font-size: 11px; text-transform: uppercase; color: var(--muted); letter-spacing: .5px; margin-top: 2px; }
.th-foot   { font-size: 11px; color: var(--muted); margin-top: 8px; }
.th-foot code { background: var(--bg); padding: 1px 6px; border-radius: var(--radius-xs); font-size: 11px; }

.btn-warn {
  background: var(--warn);
  color: white;
  border-color: var(--warn);
}
.btn-warn:hover { filter: brightness(0.95); }

/* AI summary card (Sprint I A2) */
.ai-summary { border-left: 3px solid var(--primary); }
.ai-hint    { font-size: 11.5px; color: var(--muted); font-weight: 400; }
.ai-empty   { font-size: 12.5px; color: var(--muted); margin: 0; line-height: 1.6; }
.ai-output {
  font-size: 13.5px;
  line-height: 1.65;
  color: var(--text);
  background: var(--bg);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  padding: 12px 16px;
  white-space: pre-wrap;
  word-break: break-word;
}
.ai-provider {
  font-size: 10.5px;
  color: var(--muted);
  margin-top: 8px;
  font-family: "SF Mono", monospace;
}
</style>
