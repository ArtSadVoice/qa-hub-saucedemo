<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { apiCall } from '@/api/client'
import { useToast } from '@/composables/useToast'
import { useProjectStore } from '@/stores/projects'
import { useSSE } from '@/composables/useSSE'
import { usePipelineStore } from '@/stores/pipeline'
import TipBanner from '@/components/TipBanner.vue'
import { copyTextWithFallback } from '@/utils/clipboard'
import ProgressStrip from '@/components/pipeline/ProgressStrip.vue'
import MiniReleaseGate from '@/components/pipeline/MiniReleaseGate.vue'
import BugDetectPanel from '@/components/BugDetectPanel.vue'
import { useConfirm } from '@/composables/useConfirm'
import type { PreflightReport } from '@/api/types'

const preflightCheck = ref<PreflightReport | null>(null)
const preflightChecking = ref(false)
async function runPreflight(): Promise<boolean> {
  if (!projects.current) return true
  preflightChecking.value = true
  try {
    const r = await apiCall<PreflightReport>(
      `/api/preflight/${projects.current}`,
      { silent: true },
    )
    preflightCheck.value = r
    if (r.ok) return true
    // Build a friendly diagnostic
    const lines = []
    if (r.excel_locks.length) {
      lines.push(`Excel มี ${r.excel_locks.length} ไฟล์เปิดอยู่: ${r.excel_locks.join(', ')}`)
    }
    if (!r.template.exists) {
      lines.push('Template ไม่อยู่ใน templates/Test_Result_Template.docx')
    } else if (r.template.issues.length) {
      lines.push(`Template มี ${r.template.issues.length} structural issue:`)
      for (const i of r.template.issues) lines.push(`  - ${i}`)
    }
    const ok = await confirm({
      title: 'Preflight failed — รัน pipeline ต่อหรือยกเลิก?',
      desc: lines.join('\n') +
        '\n\nแนะนำให้แก้ก่อน — ถ้ารัน pipeline ตอนนี้ Excel/template อาจ corrupt.',
      okLabel: 'รันต่อทั้งที่ยังเตือน',
      cancelLabel: 'ยกเลิก',
      danger: true,
    })
    return ok
  } catch {
    // Network/API issue — don't block pipeline run on this gate
    return true
  } finally {
    preflightChecking.value = false
  }
}

const pipeline = usePipelineStore()
const { confirm } = useConfirm()
const projects = useProjectStore()
const toast = useToast()

type PipelineMode = 'full' | 'manual' | 'report'
const mode = ref<PipelineMode>('full')

interface ModeOption { id: PipelineMode; label: string; hint: string }

// Modes vary by project type — tests-only types (playwright-only / pytest-only)
// have nothing to filter; manual-testing has no Playwright stages so the
// remaining modes would collapse.
const availableModes = computed<ModeOption[]>(() => {
  const t = projects.currentMeta?.type
  if (t === 'playwright-only' || t === 'pytest-only') return []
  if (t === 'manual-testing') return [
    { id: 'full',   label: 'Full',         hint: 'all manual stages' },
    { id: 'report', label: 'Report Only',  hint: 'stages 6–9' },
  ]
  // full-pipeline (default)
  return [
    { id: 'full',   label: 'Full',         hint: 'all stages' },
    { id: 'manual', label: 'Manual TCM',   hint: 'no Playwright' },
    { id: 'report', label: 'Report Only',  hint: 'stages 6–9' },
  ]
})

// Snap mode back to a valid option when the project (and therefore the mode set) changes
watch(availableModes, (modes) => {
  if (!modes.length) return
  if (!modes.find((m) => m.id === mode.value)) mode.value = modes[0].id
})

const showBugDetect = ref(false)

interface StageStatus {
  ok: boolean
  count?: number
  file?: string | null
  files?: string[]
  stale?: boolean
}
interface PipelineStatus {
  s1?: StageStatus; s2?: StageStatus; s3?: StageStatus
  s4?: StageStatus; s5?: StageStatus; s6?: StageStatus
  s7?: StageStatus; s8?: StageStatus; s9?: StageStatus
}

const status = ref<PipelineStatus>({})
const tag = ref<'all' | 'smoke' | 'e2e' | 'regression' | 'visual'>('all')
const env = ref<'uat' | 'prod'>('uat')
const activeStage = ref<string>('')

const sse = useSSE()
const logLines = computed(() => sse.lines.value)
const logBox = ref<HTMLPreElement | null>(null)

watch(logLines, () => {
  // Auto-scroll log to bottom on new line
  setTimeout(() => {
    if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
  }, 30)
}, { deep: true })

interface StageDef {
  id: string
  num: number
  label: string
  descTh?: string                  // Thai description shown under the stage row
  ok_label: (s: StageStatus | undefined) => string
  endpoint?: string
  hideForType?: string[]
  onlyForType?: string[]           // Restrict stage to a subset of project types (e.g. s0 only for playwright projects)
  needsTagEnv?: boolean
  manual?: boolean                 // No endpoint — just a reminder card with copy-path button
  folderHint?: 'input' | 'output' | 'requirements' | 'figma' | 'screenshots'
}

// Stage layout matches legacy templates/dashboard.html (Sprint J — parity audit).
// Fields:
//   manual=true  → no endpoint, just a reminder card with copy-path helpers
//   needsTagEnv  → wires the Tag/Env selectors above into the run URL (s5 only)
//   onlyForType  → restrict to one project type (s0 only — survey-app projects)
const STAGES: StageDef[] = [
  { id: 's0', num: 0, label: 'Explore Survey Paths',
    descTh: 'Playwright MCP เดิน survey ทุก branch path → สร้าง requirements/survey_map.md + FLOW.md ก่อน BA Agent',
    endpoint: '/api/run/explore',
    onlyForType: ['playwright-only', 'full-pipeline'],
    ok_label: (s) => s?.ok ? `✓ survey_map.md ready` : 'survey-app project? click to run' },
  { id: 's1', num: 1, label: 'เตรียมไฟล์ Input',
    descTh: 'วาง requirement (.md) ใน requirements/ และ/หรือ Figma (.png) ใน figma/',
    manual: true,
    folderHint: 'requirements',
    ok_label: (s) => s?.ok ? `✓ ${s.files?.length || 1} input file(s)` : 'Drop files into requirements/ or figma/' },
  { id: 's2', num: 2, label: 'BA Agent → สร้าง Excel TCM',
    descTh: 'BA Agent วิเคราะห์ requirement → ba_output.json → generate_tcm.py สร้าง Excel TCM 3 sheets (deterministic)',
    // Sprint J F2 — match legacy `/api/run/ba` (orchestrator.py --skip-playwright).
    // Vue v2 used to call `/api/run/generate` (run.py) which is a different script.
    endpoint: '/api/run/ba',
    ok_label: (s) => s?.ok ? `✓ TCM ready (${s.file})` : 'no TCM yet' },
  { id: 's3', num: 3, label: 'Review & แก้ไข Excel + Add Charts',
    descTh: 'เปิด Excel → Sheet PROJECT_INFO/SUMMARY/TCM → review + กรอก project info → 📊 Add Charts → 🔍 Review TCM (AI)',
    endpoint: '/api/run/add-charts',
    folderHint: 'input',
    ok_label: (s) => s?.ok ? `✓ charts injected into ${s.file}` : 'TCM needs charts' },
  { id: 's4', num: 4, label: 'Generate Spec Files (Playwright)',
    descTh: 'สร้าง test script จาก Excel TCM ที่ review แล้ว — ใช้ ba_output จาก Stage 2',
    endpoint: '/api/run/spec',
    hideForType: ['manual-testing'],
    ok_label: (s) => s?.ok ? `✓ ${s.count} spec file(s)${s.stale ? ' (stale!)' : ''}` : 'no spec yet' },
  { id: 's5', num: 5, label: 'Run Tests + Screenshots (Playwright)',
    descTh: 'รัน Playwright tests + บันทึก screenshot ทุก test case อัตโนมัติ',
    endpoint: '/api/run/tests',
    hideForType: ['manual-testing'],
    needsTagEnv: true,
    folderHint: 'screenshots',
    ok_label: (s) => s?.ok ? `✓ ${s.count} screenshots from last run` : 'no run history' },
  { id: 's6', num: 6, label: 'อัปเดตผล Test ใน Excel',
    descTh: 'เปิด Excel → Sheet TCM → กรอก Column J (Status) + K (Executed Date) → บันทึกปิด ก่อนรัน Stage 7',
    manual: true,
    folderHint: 'input',
    ok_label: (s) => s?.ok ? '✓ status filled' : 'fill TCM Status column' },
  { id: 's7', num: 7, label: 'Generate Word Report',
    descTh: 'สร้าง Word test result report จาก Excel ที่อัปเดตแล้ว พร้อมสร้าง chart PNG',
    endpoint: '/api/run/generate',
    folderHint: 'output',
    ok_label: (s) => s?.ok ? `✓ report ready (${s.file})` : 'no report yet' },
  { id: 's8', num: 8, label: 'Inject Screenshots → Word',
    descTh: 'แนบรูป chart_summary.png + screenshot ทุก test case เข้า Word output อัตโนมัติ',
    endpoint: '/api/run/inject',
    folderHint: 'screenshots',
    ok_label: (s) => s?.ok ? '✓ screenshots injected into report' : 'inject after Stage 7' },
  { id: 's9', num: 9, label: 'Download + Send Report',
    descTh: 'ดาวน์โหลด Word report พร้อมส่งทาง Email / Slack — ตั้งค่าผู้รับใน Settings → Email',
    folderHint: 'output',
    ok_label: (s) => s?.ok ? `✓ ready to download` : 'no report' },
]

const visibleStages = computed(() => {
  const t = projects.currentMeta?.type
  let list = STAGES
  if (t === 'playwright-only') list = STAGES.filter((s) => s.id === 's5' || s.id === 's0')
  else if (t === 'pytest-only') list = STAGES.filter(
    (s) => ['s5', 's7', 's8', 's9'].includes(s.id),
  )
  else if (t) list = STAGES.filter((s) => !s.hideForType?.includes(t))
  // Some stages restrict to a subset of project types
  if (t) list = list.filter((s) => !s.onlyForType || s.onlyForType.includes(t))

  // Apply mode filter on top of type-aware filter
  if (mode.value === 'manual') {
    // Hide Playwright spec/test stages even on full-pipeline projects
    list = list.filter((s) => s.id !== 's4' && s.id !== 's5')
  } else if (mode.value === 'report') {
    // Report-only: stages 7, 8, 9 (matches legacy)
    list = list.filter((s) => ['s7', 's8', 's9'].includes(s.id))
  }
  return list
})

async function loadStatus() {
  if (!projects.current) return
  try {
    status.value = await apiCall<PipelineStatus>(`/api/status?p=${projects.current}`)
  } catch { /* apiCall toasted */ }
}

async function runStage(stage: StageDef) {
  if (!projects.current || !stage.endpoint) return
  // Pre-pipeline gate: block run if Excel files locked or template broken,
  // unless user explicitly chooses to proceed.
  const ok = await runPreflight()
  if (!ok) return
  const params = new URLSearchParams({ p: projects.current })
  if (stage.needsTagEnv) {
    if (tag.value !== 'all') params.set('tag', tag.value)
    if (env.value !== 'uat') params.set('env', env.value)
  }
  activeStage.value = stage.id
  pipeline.start(`Stage ${stage.num}`)
  const url = `${stage.endpoint}?${params}`
  sse.start(url, {
    onMessage: () => { /* lines auto-pushed by composable */ },
    onClose: () => {
      // Detect failure from the last line of the SSE log
      const lastLine = sse.lines.value[sse.lines.value.length - 1] || ''
      let success = true
      try {
        const data = JSON.parse(lastLine)
        if (data.returncode && data.returncode !== 0) success = false
        if (data.type === 'err' || data.type === 'error') success = false
      } catch { /* not JSON — leave as success */ }
      pipeline.finish(success)
      activeStage.value = ''
      loadStatus()
    },
  })
}

// ── Sprint J F3 — 🔍 Review TCM (AI) — runs scripts/review_excel.py via SSE
async function runReviewExcel() {
  if (!projects.current) return
  activeStage.value = 's3'
  pipeline.start('Review TCM (AI)')
  sse.start(`/api/run/review-excel?p=${projects.current}`, {
    onClose: () => { activeStage.value = ''; pipeline.finish(true) },
  })
}

// ── Sprint J F6 — 📋 Copy folder path to clipboard.
// Mirrors FilesView / ScreenshotsView wording so the toast tells users what
// to do next (paste into Win+R / Explorer address bar). Browser security
// prevents Hub from actually launching Explorer, so the label is intentionally
// "Copy path" — not "Open folder".
//
// Two failure modes need separate handling:
//   1. API can't resolve the path (project missing / kind invalid) →
//      "Couldn't resolve" makes sense.
//   2. Clipboard write throws (DevTools focused, iframe sandbox, etc.) →
//      we have the path; show it so the user can copy it by hand.
// The previous single try/catch coalesced both, leaving users with the
// misleading "Couldn't resolve" toast when the API call had actually
// succeeded.
async function copyFolderPath(kind: NonNullable<StageDef['folderHint']>) {
  if (!projects.current) return
  let path = ''
  try {
    const r = await apiCall<{ path: string }>(`/api/path/${kind}?p=${projects.current}`, { silent: true })
    path = r.path || ''
  } catch {
    toast.show(`Couldn't resolve ${kind}/ path`, 'err')
    return
  }
  if (!path) {
    toast.show(`No path returned for ${kind}/`, 'err')
    return
  }
  const ok = await copyTextWithFallback(path)
  if (ok) {
    toast.show(`📋 คัดลอก path ${kind}/ — วางใน Win+R หรือ Explorer address bar:\n${path}`, 'ok')
  } else {
    toast.show(`Clipboard ใช้ไม่ได้ — คัดลอก path นี้เอง:\n${path}`, 'warn', 12000)
  }
}

async function cancelRun() {
  try {
    await apiCall('/api/run/cancel', { body: { project_id: projects.current } })
    sse.stop()
    activeStage.value = ''
  } catch { /* apiCall toasted */ }
}

// Sprint J F4 — `/api/run/all` actually runs `run.py` (Stage 7) THEN
// `screenshot_injector.py` (Stage 8). Legacy labelled this "Report + Inject"
// — Vue v2 used to call it "Run All" which was misleading.
async function runReportInject() {
  if (!projects.current) return
  const ok = await confirm({
    title: 'Run Report + Inject?',
    desc: 'รัน Stage 7 (Generate Word Report) + Stage 8 (Inject Screenshots) ต่อเนื่อง — ข้าม Stages อื่น',
    okLabel: '⚡ Report + Inject',
  })
  if (!ok) return
  const params = new URLSearchParams({ p: projects.current })
  if (tag.value !== 'all') params.set('tag', tag.value)
  if (env.value !== 'uat') params.set('env', env.value)
  activeStage.value = 'all'
  pipeline.start('Report + Inject')
  sse.start(`/api/run/all?${params}`, {
    onClose: () => {
      const lastLine = sse.lines.value[sse.lines.value.length - 1] || ''
      let success = true
      try {
        const data = JSON.parse(lastLine)
        if (data.returncode && data.returncode !== 0) success = false
      } catch {}
      pipeline.finish(success)
      activeStage.value = ''
      loadStatus()
    },
  })
}

const showSendReport = ref(false)
const sendReportForm = reactive({
  scope: 'all' as 'all' | 'changed-only',
  recipients_override: '',
})
async function sendReport() {
  try {
    await apiCall('/api/run/send-report', {
      body: {
        project_id: projects.current,
        scope: sendReportForm.scope,
        recipients_override: sendReportForm.recipients_override.trim() || undefined,
      },
    })
    toast.show('📤 Report sent — check email', 'ok')
    showSendReport.value = false
  } catch { /* apiCall toasted */ }
}

// ── Watch mode (auto-rerun on file change) ─────────────────────────────
const watchOn = ref(false)
const watchInfo = ref<{ active: boolean; pid?: number; started_at?: string } | null>(null)

async function loadWatchStatus() {
  try {
    watchInfo.value = await apiCall(`/api/run/watch/status?p=${projects.current}`, { silent: true })
    watchOn.value = !!watchInfo.value?.active
  } catch { /* watch may not be supported */ }
}

async function toggleWatch() {
  if (!projects.current) return
  try {
    const action = watchOn.value ? 'stop' : 'start'
    await apiCall('/api/run/watch', {
      body: { project_id: projects.current, action, tag: tag.value, env: env.value },
    })
    toast.show(action === 'start' ? '👁️ Watch mode started' : '⏹️ Watch mode stopped', 'ok')
    await loadWatchStatus()
  } catch { /* apiCall toasted */ }
}

// ── Debug headed (--headed --debug) ─────────────────────────────────────
const debugHeaded = ref(false)
const debugSpec = ref('')

function runDebugHeaded() {
  if (!projects.current) return
  const params = new URLSearchParams({ p: projects.current, headed: '1' })
  const target = debugSpec.value.trim() || lastFailedTests.value.join('|')
  if (target) params.set('grep', target)
  if (env.value !== 'uat') params.set('env', env.value)
  activeStage.value = 's5'
  pipeline.start('Debug (headed)')
  sse.start(`/api/run/tests?${params}`, {
    onClose: () => { activeStage.value = ''; pipeline.finish(true); loadStatus() },
  })
}

// ── Excel TCM validation ─────────────────────────────────────────────────
interface ExcelStats {
  total: number; filled: number; not_started: number
  counts: Record<string, number>
  missing_shots: string[]; shot_coverage: number
}
const excelStats = ref<ExcelStats | null>(null)
const excelLoading = ref(false)
const excelError = ref('')

async function validateExcel() {
  if (!projects.current) return
  excelLoading.value = true
  excelError.value = ''
  excelStats.value = null
  try {
    excelStats.value = await apiCall<ExcelStats>(`/api/validate/excel?p=${projects.current}`, { silent: true })
  } catch (e: any) {
    excelError.value = e?.message || 'Failed to validate'
  } finally {
    excelLoading.value = false
  }
}

const excelPct = computed(() => {
  if (!excelStats.value || !excelStats.value.total) return 0
  return Math.round((excelStats.value.filled / excelStats.value.total) * 100)
})
const shotPct = computed(() => {
  if (!excelStats.value || !excelStats.value.total) return 0
  return Math.round((excelStats.value.shot_coverage / excelStats.value.total) * 100)
})

// ── Retrofit TCM (playwright-only → generate TCM from spec files) ───────
const retrofitting = ref(false)
async function retrofitTcm() {
  if (!projects.current) return
  const ok = await confirm({
    title: 'Retrofit TCM?',
    desc: 'Generate TCM Excel จาก .spec.ts ที่มีอยู่ — จะสร้างไฟล์ใหม่ใน input/',
    okLabel: '🔧 Retrofit',
  })
  if (!ok) return
  retrofitting.value = true
  try {
    const r = await apiCall<{ ok: boolean; tcid_count?: number; output?: string; error?: string }>(
      '/api/tools/retrofit-tcm',
      { body: { project_id: projects.current } }
    )
    if (r.ok) {
      toast.show(`✓ Retrofit OK — ${r.tcid_count || 0} TC(s) → ${r.output || 'TCM ready'}`, 'ok')
      loadStatus()
    } else {
      toast.show(`Retrofit failed: ${r.error || 'unknown'}`, 'err')
    }
  } catch { /* apiCall toasted */ } finally {
    retrofitting.value = false
  }
}

// ── Per-stage file expansion ────────────────────────────────────────────
const expandedStage = ref<string>('')
function toggleStage(id: string) {
  expandedStage.value = expandedStage.value === id ? '' : id
}
function stageFiles(id: string): string[] {
  const s = status.value[id as keyof PipelineStatus]
  if (!s) return []
  if (Array.isArray(s.files) && s.files.length) return s.files
  if (s.file) return [s.file]
  return []
}

// ── Re-run failed tests ────────────────────────────────────────────────
const lastFailedTests = ref<string[]>([])

watch(() => sse.finished.value, (done) => {
  if (!done || activeStage.value) return
  // Parse log for failed test names — Playwright outputs like
  //   ✘  1) [chromium] › TS_001 → step name (or similar)
  //   FAIL TS_002
  const failed: string[] = []
  for (const raw of sse.lines.value) {
    const data = parseLine(raw)
    const line = data.line || ''
    const m1 = line.match(/[✘✗×]\s+\d*\s*\)?\s*(?:\[[^\]]*\]\s*[›>]\s*)?([\w-]+\.spec\.ts|TS_\d+_\d+)/)
    if (m1) failed.push(m1[1])
  }
  lastFailedTests.value = [...new Set(failed)]
})

function rerunFailed() {
  if (!lastFailedTests.value.length || !projects.current) return
  const grep = lastFailedTests.value.join('|')
  const params = new URLSearchParams({ p: projects.current, grep })
  if (env.value !== 'uat') params.set('env', env.value)
  activeStage.value = 's5'
  sse.start(`/api/run/tests?${params}`, {
    onClose: () => { activeStage.value = ''; loadStatus() },
  })
}

function parseLine(raw: string): { line: string; type?: string; done?: boolean; returncode?: number } {
  try {
    return JSON.parse(raw)
  } catch {
    return { line: raw }
  }
}

function lineColor(t?: string): string {
  if (t === 'err' || t === 'error') return '#F85149'
  if (t === 'warn' || t === 'warning') return '#E3B341'
  if (t === 'ok' || t === 'success') return '#56D364'
  if (t === 'info') return '#58A6FF'
  return '#C9D1D9'
}

// Apply Command Palette / deep-link query params:
//   ?action=send-report → open the Send Report modal once project + status loaded
//   ?action=run-all     → trigger the Run All flow (with confirm dialog)
const route = useRoute()
async function applyQueryAction() {
  const a = route.query.action
  if (!a || !projects.current) return
  await nextTick()
  if (a === 'send-report') showSendReport.value = true
  else if (a === 'run-all') runReportInject()
}

onMounted(async () => {
  if (!projects.all.length) await projects.load()
  loadStatus()
  loadWatchStatus()
  applyQueryAction()
})
watch(() => projects.current, () => {
  loadStatus()
  loadWatchStatus()
})
watch(() => route.query, applyQueryAction)
</script>

<template>
  <TipBanner id="pipeline-intro" variant="tip">
    <b>Pipeline 9 stages:</b> Upload → BA → Charts → Spec → Run → Inject → Report → Open → Download.
    เลือก tag + env → กด <b>▶ Run</b> ของ stage หรือ <b>⚡ Report + Inject</b> รัน Stage 7+8 ต่อเนื่อง.
    Stage ที่ ✓ สีเขียวคือพร้อมใช้แล้ว.
  </TipBanner>
  <TipBanner id="pipeline-prod-warning" variant="warn" persistent v-if="env === 'prod'">
    <b>🔴 Prod environment:</b> test อาจ write data จริง — แนะนำใช้ <code>@smoke</code> tag เท่านั้นใน prod
  </TipBanner>

  <!-- Mini Release Gate (sticky context for QA) -->
  <MiniReleaseGate />

  <!-- Pipeline mode selector — adapts to project type -->
  <div v-if="availableModes.length > 1" class="mode-bar">
    <span class="mode-label">Mode:</span>
    <button v-for="m in availableModes" :key="m.id"
            class="mode-btn" :class="{ active: mode === m.id }"
            @click="mode = m.id">
      {{ m.label }} <span class="mode-hint">{{ m.hint }}</span>
    </button>
  </div>
  <div v-else-if="!availableModes.length && projects.currentMeta?.type === 'playwright-only'" class="mode-bar">
    <span class="mode-label">Mode:</span>
    <span class="mode-fixed">▶ Stage 5 only — playwright-only project</span>
  </div>
  <div v-else-if="!availableModes.length && projects.currentMeta?.type === 'pytest-only'" class="mode-bar">
    <span class="mode-label">Mode:</span>
    <span class="mode-fixed">▶ Stages 5/7/8/9 — pytest-only project</span>
  </div>

  <!-- Progress strip — sticky -->
  <ProgressStrip :stages="visibleStages" :status="status" :active-stage="activeStage" />

  <!-- Project type indicator -->
  <div v-if="projects.currentMeta" class="card type-banner">
    <strong>{{ projects.currentMeta.name }}</strong>
    <span class="type-pill">{{ projects.currentMeta.type }}</span>
    <span v-if="projects.currentMeta.type === 'playwright-only'" class="type-note">— Stage 5 only</span>
    <span v-else-if="projects.currentMeta.type === 'pytest-only'" class="type-note">— Stages 5/7/8/9</span>
    <span v-else-if="projects.currentMeta.type === 'manual-testing'" class="type-note">— Stages 4, 5 hidden</span>
  </div>

  <!-- Tag + env selectors (for stage 5) -->
  <div class="card">
    <div class="card-title">Test scope &amp; quick actions</div>
    <div class="scope-row">
      <div class="field">
        <label>Tag</label>
        <select v-model="tag">
          <option value="all">all</option>
          <option value="smoke">@smoke</option>
          <option value="e2e">@e2e</option>
          <option value="regression">@regression</option>
          <option value="visual">@visual</option>
        </select>
      </div>
      <div class="field">
        <label>Environment</label>
        <select v-model="env" :class="{ 'env-prod': env === 'prod' }">
          <option value="uat">🟢 UAT</option>
          <option value="prod">🔴 Prod</option>
        </select>
      </div>
      <div class="quick-actions">
        <button class="btn btn-primary" @click="runReportInject" :disabled="sse.connected.value"
                title="รัน /api/run/all = Stage 7 (Generate Report) + Stage 8 (Inject Screenshots)">
          ⚡ Report + Inject
        </button>
        <button class="btn" @click="showSendReport = true" :disabled="sse.connected.value" style="background:var(--success-soft);color:var(--success);border-color:var(--success)">📤 Send Report</button>
        <button class="btn watch-btn" :class="{ on: watchOn }" @click="toggleWatch"
                :title="watchOn ? 'Watch mode active — re-runs on file change' : 'Watch mode off'">
          {{ watchOn ? '👁️ Watching' : '👁️ Watch' }}
        </button>
        <button class="btn" @click="loadStatus">↻ Refresh</button>
      </div>
    </div>
    <!-- Re-run failed tests offer (after a stage 5 completes with failures) -->
    <div v-if="lastFailedTests.length && !sse.connected.value" class="rerun-banner">
      <span>🔁 Last run had <b>{{ lastFailedTests.length }}</b> failing test(s)</span>
      <button class="btn btn-sm" @click="rerunFailed">▶ Re-run failed only</button>
      <button class="btn btn-sm" @click="showBugDetect = true">🐛 Log as bugs…</button>
      <button class="btn btn-sm" @click="lastFailedTests = []" title="Dismiss">×</button>
    </div>
  </div>

  <!-- Bug detection panel — opens on demand after failures -->
  <BugDetectPanel v-if="showBugDetect && lastFailedTests.length"
                  :failed-tests="lastFailedTests"
                  :project-id="projects.current"
                  @dismiss="showBugDetect = false"
                  @logged="showBugDetect = false; lastFailedTests = []" />

  <!-- 🛠 Pipeline Tools: Debug · Excel validation · Retrofit TCM -->
  <div class="card tools-card">
    <div class="card-title">🛠 Pipeline Tools</div>

    <!-- Debug mode (headed) -->
    <div class="tool-row">
      <div class="tool-info">
        <div class="tool-title">🐞 Debug Mode (headed)</div>
        <div class="tool-desc">รัน Playwright แบบเปิด browser + debug pause — เหมาะสำหรับเจาะ test ที่ล้ม</div>
      </div>
      <div class="tool-actions">
        <input v-model="debugSpec" type="text" placeholder="Spec or pattern (เว้นว่าง = re-run failed)"
               style="min-width:220px;font-size:12.5px" />
        <button class="btn btn-sm" :disabled="sse.connected.value" @click="runDebugHeaded">
          ▶ Debug
        </button>
      </div>
    </div>

    <!-- Excel TCM validation -->
    <div class="tool-row">
      <div class="tool-info">
        <div class="tool-title">📊 Excel TCM Validation</div>
        <div class="tool-desc">ตรวจสอบความครบถ้วนของ TCM Excel: filled %, screenshot coverage, status breakdown</div>
        <div v-if="excelStats" class="excel-results">
          <div class="excel-row">
            <span>Filled: <b>{{ excelStats.filled }}/{{ excelStats.total }}</b></span>
            <div class="bar"><div class="fill" :style="{ width: excelPct + '%' }"></div></div>
            <span class="pct">{{ excelPct }}%</span>
          </div>
          <div class="excel-row">
            <span>Screenshots: <b>{{ excelStats.shot_coverage }}/{{ excelStats.total }}</b></span>
            <div class="bar"><div class="fill warn" :style="{ width: shotPct + '%' }"></div></div>
            <span class="pct">{{ shotPct }}%</span>
          </div>
          <div class="status-pills">
            <span v-for="(n, k) in excelStats.counts" :key="k" v-show="n > 0" class="pill">
              {{ k }}: <b>{{ n }}</b>
            </span>
          </div>
          <div v-if="excelStats.missing_shots.length" class="missing">
            <b>{{ excelStats.missing_shots.length }}</b> TC ไม่มี screenshot:
            <code>{{ excelStats.missing_shots.slice(0, 5).join(', ') }}{{ excelStats.missing_shots.length > 5 ? '…' : '' }}</code>
          </div>
        </div>
        <div v-if="excelError" class="excel-error">{{ excelError }}</div>
      </div>
      <div class="tool-actions">
        <button class="btn btn-sm" :disabled="excelLoading" @click="validateExcel">
          {{ excelLoading ? 'Checking…' : '✓ Validate' }}
        </button>
      </div>
    </div>

    <!-- Retrofit TCM (playwright-only) -->
    <div v-if="projects.currentMeta?.type === 'playwright-only'" class="tool-row">
      <div class="tool-info">
        <div class="tool-title">🔧 Retrofit TCM</div>
        <div class="tool-desc">Generate TCM Excel จาก .spec.ts files — สำหรับ playwright-only projects ที่ยังไม่มี TCM</div>
      </div>
      <div class="tool-actions">
        <button class="btn btn-sm" :disabled="retrofitting" @click="retrofitTcm">
          {{ retrofitting ? 'Generating…' : '🔧 Retrofit' }}
        </button>
      </div>
    </div>
  </div>

  <!-- Send Report modal -->
  <Teleport to="body">
    <div v-if="showSendReport" class="modal-overlay" @click.self="showSendReport = false">
      <div class="modal-box">
        <div class="modal-header">
          <h3>📤 Send Report via Email</h3>
          <button class="x" @click="showSendReport = false">&times;</button>
        </div>
        <div class="modal-body">
          <div class="field" style="margin-bottom:10px">
            <label>Scope</label>
            <select v-model="sendReportForm.scope" style="width:100%">
              <option value="all">All scenarios</option>
              <option value="changed-only">Changed scenarios only</option>
            </select>
          </div>
          <div class="field" style="margin-bottom:14px">
            <label>Recipients override (optional, comma-separated)</label>
            <input v-model="sendReportForm.recipients_override" placeholder="leave empty = use Settings → Email recipients" style="width:100%" />
          </div>
          <div style="display:flex;gap:8px;justify-content:flex-end">
            <button class="btn" @click="showSendReport = false">Cancel</button>
            <button class="btn btn-primary" @click="sendReport">📤 Send</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- Stage list -->
  <div class="card">
    <div class="card-title">Pipeline Stages</div>
    <div class="stages">
      <div v-for="s in visibleStages" :key="s.id" class="stage-wrap">
        <div class="stage"
             :class="{
               ok: status[s.id as keyof PipelineStatus]?.ok,
               active: activeStage === s.id,
               manual: s.manual,
             }">
          <div class="stage-num">{{ s.num }}</div>
          <div class="stage-body">
            <div class="stage-label">
              <span v-if="s.manual" class="badge-manual">🧑 ทำเอง</span>
              <span v-else-if="s.endpoint" class="badge-auto">🤖 รันคำสั่ง</span>
              {{ s.label }}
            </div>
            <div v-if="s.descTh" class="stage-desc">{{ s.descTh }}</div>
            <div class="stage-status">{{ s.ok_label(status[s.id as keyof PipelineStatus]) }}</div>
          </div>
          <div class="stage-actions">
            <!-- 📋 Copy folder path (Sprint J F6).
                 Browser can't launch Explorer; this copies the absolute path
                 to clipboard so user pastes into Win+R / Explorer address bar. -->
            <button v-if="s.folderHint" class="btn btn-sm copy-path"
                    @click="copyFolderPath(s.folderHint)"
                    :title="`คัดลอก absolute path ของ ${s.folderHint}/ ไป clipboard — วางใน Win+R หรือ Explorer address bar`">
              📋 Copy {{ s.folderHint }}/ path
            </button>
            <!-- 🔍 Review TCM AI button on Stage 3 (Sprint J F3) -->
            <button v-if="s.id === 's3'" class="btn btn-sm review-tcm"
                    :disabled="sse.connected.value || !projects.current"
                    @click="runReviewExcel"
                    title="AI วิเคราะห์คุณภาพ test cases ใน Excel TCM">
              🔍 Review TCM
            </button>
            <button v-if="stageFiles(s.id).length" class="btn-icon"
                    :class="{ open: expandedStage === s.id }"
                    @click="toggleStage(s.id)"
                    :title="`${stageFiles(s.id).length} file(s)`">
              <span class="caret">▸</span>
              <span class="count">{{ stageFiles(s.id).length }}</span>
            </button>
            <!-- Send Report inline at Stage 9 (Sprint J F5) -->
            <button v-if="s.id === 's9'" class="btn btn-sm send-report"
                    :disabled="sse.connected.value || !projects.current"
                    @click="showSendReport = true"
                    title="ส่ง Word report ทาง Email + Slack">
              📤 Send Report
            </button>
            <button v-if="s.endpoint" class="btn btn-sm"
                    :disabled="sse.connected.value || !projects.current"
                    @click="runStage(s)">
              <span v-if="activeStage === s.id">⏳ running</span>
              <span v-else>▶ Run</span>
            </button>
            <span v-else-if="s.manual" class="manual-tag">manual</span>
          </div>
        </div>
        <div v-if="expandedStage === s.id" class="stage-files">
          <ul>
            <li v-for="f in stageFiles(s.id)" :key="f" :title="f">
              <span class="file-icon">📄</span>
              <span class="file-name">{{ f }}</span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  </div>

  <!-- Live log (only when running) -->
  <div v-if="sse.connected.value || sse.lines.value.length" class="card log-card">
    <div class="card-title" style="display:flex;align-items:center">
      <template v-if="sse.connected.value">⏳ Running stage {{ activeStage }}</template>
      <template v-else>📜 Last run output ({{ activeStage || 'completed' }})</template>
      <button v-if="sse.connected.value" class="btn btn-sm btn-danger" @click="cancelRun" style="margin-left:auto">
        ⏹ Cancel
      </button>
      <button v-else class="btn btn-sm" @click="sse.lines.value = []" style="margin-left:auto">
        Clear
      </button>
    </div>
    <div ref="logBox" class="log" role="log" aria-live="polite">
      <div v-for="(raw, i) in sse.lines.value" :key="i" class="log-line"
           :style="{ color: lineColor(parseLine(raw).type) }">{{ parseLine(raw).line || ' ' }}</div>
      <div v-if="!sse.lines.value.length" class="log-empty">— ยังไม่มี output —</div>
    </div>
  </div>
</template>

<style scoped>
.type-banner { display: flex; gap: 10px; align-items: center; padding: 10px 16px; background: var(--bg); }

.mode-bar {
  display: flex;
  gap: 6px;
  align-items: center;
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
}
.mode-label {
  font-size: 11px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
  margin-right: 6px;
}
.mode-btn {
  background: var(--card);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  padding: 6px 12px;
  font-size: 12.5px;
  font-family: inherit;
  cursor: pointer;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all var(--duration-fast) var(--ease);
}
.mode-btn:hover { background: var(--bg); }
.mode-btn.active {
  background: var(--primary);
  color: white;
  border-color: var(--primary);
  font-weight: 600;
}
.mode-btn .mode-hint { opacity: 0.6; font-size: 11px; }
.mode-btn.active .mode-hint { opacity: 0.85; }

@media (max-width: 640px) {
  /* MODE toggle: hide the "MODE:" label and the per-button hint
     ("all stages" / "no Playwright" / etc.) so 3 buttons fit one row. */
  .mode-label { display: none; }
  .mode-btn { padding: 8px 12px; font-size: 12px; flex: 1 1 0; min-height: 40px; justify-content: center; }
  .mode-btn .mode-hint { display: none; }
  /* Stage cards: action buttons wrap below the title row instead of
     pushing the card past viewport. flex-basis:100% forces the action
     row onto its own line below stage-title. */
  .stage-actions { flex-basis: 100%; gap: 6px; margin-top: 6px; }
  .stage-actions .btn-sm { flex: 1 1 auto; min-width: 0; justify-content: center; }
}
.mode-fixed {
  font-size: 12.5px;
  color: var(--text-secondary, var(--text));
  background: var(--primary-soft);
  border-radius: var(--radius-sm);
  padding: 5px 12px;
  font-weight: 600;
}
.type-pill { font-size: 11px; padding: 2px 8px; background: #E3F2FD; color: var(--primary); border-radius: 10px; font-weight: 700; }  /* stylelint-disable-line color-no-hex */
.type-note { color: var(--muted); font-size: 12px; }

.scope-row { display: flex; gap: 14px; align-items: end; flex-wrap: wrap; max-width: 1100px; }
.scope-row .field { min-width: 140px; }
.scope-row .field select { width: 100%; max-width: 180px; }
.field label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; font-weight: 600; }
.field select.env-prod { color: var(--danger); font-weight: 700; }
.quick-actions { display: flex; gap: 6px; margin-left: auto; }
.watch-btn.on { background: #FFF8E1; color: var(--warn); border-color: var(--warn-soft); }  /* stylelint-disable-line color-no-hex */
.rerun-banner {
  margin-top: 12px;
  padding: 10px 14px;
  background: #FFF8E1;  /* stylelint-disable-line color-no-hex */
  border: 1px solid var(--warn-soft);
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}
.rerun-banner button:last-child {
  margin-left: auto;
  background: transparent;
  border: none;
  font-size: 16px;
  color: var(--muted);
  padding: 0 4px;
  cursor: pointer;
}

/* 🛠 Pipeline Tools panel */
.tools-card { background: var(--card); }
.tool-row {
  display: flex;
  gap: var(--space-3);
  align-items: flex-start;
  padding: var(--space-3) 0;
  border-top: 1px solid var(--border-soft);
}
.tool-row:first-of-type { border-top: none; padding-top: var(--space-2); }
.tool-info { flex: 1; min-width: 0; }
.tool-title { font-weight: 600; font-size: 13.5px; color: var(--text); margin-bottom: 2px; }
.tool-desc { font-size: 12px; color: var(--muted); line-height: 1.5; }
.tool-actions { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }

.excel-results { margin-top: 10px; display: flex; flex-direction: column; gap: 6px; }
.excel-row { display: flex; gap: 10px; align-items: center; font-size: 12.5px; }
.excel-row > span:first-child { min-width: 130px; }
.excel-row .bar {
  flex: 1; max-width: 200px; height: 6px;
  background: var(--border-soft); border-radius: 3px; overflow: hidden;
}
.excel-row .fill { height: 100%; background: var(--success); border-radius: 3px; transition: width var(--duration-slow) var(--ease); }
.excel-row .fill.warn { background: var(--warn); }
.excel-row .pct { font-weight: 600; min-width: 38px; text-align: right; }
.status-pills { display: flex; gap: 4px; flex-wrap: wrap; margin-top: 4px; }
.pill { background: var(--bg); border: 1px solid var(--border-soft); border-radius: var(--radius-md); padding: 2px 8px; font-size: 11px; color: var(--muted); }
.missing { font-size: 11.5px; color: var(--warn); margin-top: 4px; }
.missing code { background: var(--bg); padding: 1px 5px; border-radius: var(--radius-xs); font-size: 11px; }
.excel-error { color: var(--danger); font-size: 12.5px; margin-top: 6px; }

.modal-overlay {
  position: fixed; inset: 0; background: rgba(0, 0, 0, .45);
  display: flex; align-items: center; justify-content: center; z-index: 9990; padding: 20px;
}
.modal-box {
  background: var(--card); border-radius: 12px; width: 460px; max-width: 100%;
  box-shadow: 0 16px 48px rgba(0, 0, 0, .25);
}
.modal-header {
  padding: 14px 20px; border-bottom: 1px solid var(--border);
  display: flex; justify-content: space-between; align-items: center;
}
.modal-header h3 { font-size: 15px; color: var(--primary-dk); }
.x { background: none; border: none; font-size: 22px; color: var(--muted); cursor: pointer; padding: 0 4px; }
.modal-body { padding: 18px 20px; }

.stages { display: flex; flex-direction: column; gap: 6px; }
.stage { display: flex; gap: 12px; align-items: center; padding: 10px 14px; border: 1px solid var(--border); border-radius: 8px; background: white; }
.stage.ok { background: var(--success-soft); border-color: #C5E1A5; }  /* stylelint-disable-line color-no-hex */
.stage.active { background: #E3F2FD; border-color: var(--primary-soft); }  /* stylelint-disable-line color-no-hex */
.stage-num { width: 28px; height: 28px; border-radius: 50%; background: var(--text); color: white; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 13px; flex-shrink: 0; }
.stage.ok .stage-num { background: var(--success); }
.stage-body { flex: 1; min-width: 0; }
.stage-label {
  font-weight: 700;
  font-size: 13.5px;
  color: var(--text);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.stage-desc { font-size: 11.5px; color: var(--text-secondary, var(--muted)); margin-top: 3px; line-height: 1.45; }
.stage-status { font-size: 12px; color: var(--muted); margin-top: 4px; }
.stage-actions { flex-shrink: 0; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }

/* Sprint J F6 — auto / manual badges (matches legacy timeline visual) */
.badge-auto, .badge-manual {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: var(--radius-md);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
.badge-auto   { background: var(--primary-soft); color: var(--primary-dk, var(--primary)); }
.badge-manual { background: var(--warn-soft);    color: var(--warn); }
.stage.manual { background: var(--warn-soft); border-color: rgba(255, 159, 10, 0.25); }
[data-theme="dark"] .badge-manual { color: var(--warn); }

/* Sprint J F6 — 📋 Copy path button (subtler than primary actions) */
.copy-path {
  background: transparent;
  border: 1px dashed var(--border);
  color: var(--muted);
}
.copy-path:hover { color: var(--primary); border-color: var(--primary); }

/* Sprint J F3 — 🔍 Review TCM AI button (purple-tinted to distinguish AI from regular run) */
.review-tcm {
  background: var(--primary-soft);
  color: var(--primary-dk, var(--primary));
  border: 1px solid rgba(0, 113, 227, 0.3);
}
.review-tcm:hover:not(:disabled) {
  background: var(--primary);
  color: white;
  border-color: var(--primary);
}

/* Sprint J F5 — 📤 Send Report inline button at Stage 9 */
.send-report {
  background: var(--success-soft);
  color: var(--success);
  border: 1px solid rgba(48, 209, 88, 0.4);
  font-weight: 600;
}
.send-report:hover:not(:disabled) {
  background: var(--success);
  color: white;
  border-color: var(--success);
}
.manual-tag { font-size: 11px; color: var(--muted); font-style: italic; }

/* Per-stage file list */
.stage-wrap { display: flex; flex-direction: column; }
.btn-icon {
  display: inline-flex; align-items: center; gap: 4px;
  background: var(--bg);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  padding: 3px 8px; font-size: 11px;
  color: var(--muted); cursor: pointer;
  transition: all var(--duration-fast) var(--ease);
}
.btn-icon:hover { color: var(--text); border-color: var(--primary); }
.btn-icon .caret { display: inline-block; transition: transform var(--duration-fast) var(--ease); font-size: 10px; }
.btn-icon.open .caret { transform: rotate(90deg); }
.btn-icon .count { font-weight: 600; }
.stage-files {
  margin: -2px 0 6px 40px;
  padding: 8px 14px;
  background: var(--bg);
  border: 1px solid var(--border-soft);
  border-top: none;
  border-radius: 0 0 var(--radius-sm) var(--radius-sm);
  font-size: 12px;
  animation: stage-files-in var(--duration-fast) var(--ease);
}
.stage-files ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2px; }
.stage-files li { display: flex; gap: 8px; align-items: center; padding: 2px 0; }
.file-icon { opacity: 0.7; }
.file-name {
  font-family: "SF Mono", monospace; font-size: 11.5px;
  color: var(--text-secondary, var(--text));
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
@keyframes stage-files-in { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }

.log-card { padding: 12px 16px; }
.log {
  background: #0d1117;  /* stylelint-disable-line color-no-hex */
  color: #c9d1d9;  /* stylelint-disable-line color-no-hex */
  padding: 12px 14px;
  border-radius: 8px;
  font-family: 'Cascadia Mono', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  max-height: 480px;
  overflow-y: auto;
  margin: 0;
}
.log-line {
  white-space: pre-wrap;
  word-break: break-word;
  min-height: 1em;        /* keep blank lines visible without padding the whole block */
}
.log-empty {
  text-align: center;
  color: #6b7280;  /* stylelint-disable-line color-no-hex */
  padding: 24px 0;
  font-style: italic;
}
.btn-sm { padding: 4px 10px; font-size: 12px; }
</style>
