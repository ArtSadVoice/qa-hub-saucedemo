<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { useSSE } from '@/composables/useSSE'
import { useToast } from '@/composables/useToast'

// Backend /api/system-check streams two distinct event shapes:
//   per-check: {check: name, status: "ok" | "fail", detail: "…"}
//   summary:   {done: true, passed: N, total: M}
// (plus the synthetic done line that useSSE pushes on network drop:
//   {line, type:"err", done:true, returncode:-1})
interface CheckEvent {
  check?: string
  status?: 'ok' | 'fail'
  detail?: string
  done?: boolean
  passed?: number
  total?: number
  // Synthetic-error fields from useSSE
  line?: string
  type?: string
  returncode?: number
}

const sse = useSSE()
const toast = useToast()
const events = ref<CheckEvent[]>([])
const startedAt = ref<number | null>(null)
const finishedAt = ref<number | null>(null)

// Server-side check list — kept in sync with app.py's system-check generator
// so we can render the full plan as a checklist before running.
const PLAN: { name: string; desc: string }[] = [
  { name: 'Python Dependencies', desc: 'flask, openpyxl, python-docx, pandas, lxml, watchdog, dotenv' },
  { name: 'Node.js / npx',       desc: 'Playwright runner availability' },
  { name: 'Hub Config',          desc: 'config.json readable + project count' },
  { name: 'Mock Projects',       desc: '_mock-manual / _mock-full installed' },
  { name: 'Generate TCM Excel',  desc: 'create_mock_tcm.py runs end-to-end' },
  { name: 'Generate Word Report', desc: 'generate_report.py produces .docx' },
  { name: 'SMTP Connection',     desc: 'distribution.json credentials → connect + login (dry run)' },
  { name: 'Run History',         desc: 'run_history.json readable + writable' },
]

const checkEvents   = computed(() => events.value.filter((e) => !e.done && e.check))
const summaryEvent  = computed(() => events.value.find((e) => e.done))
const errorEvent    = computed(() => events.value.find((e) => e.done && e.type === 'err'))
const finished      = computed(() => !!summaryEvent.value && !sse.connected.value)

// Derived counts so progress UI doesn't have to wait for the summary line
const counts = computed(() => {
  let pass = 0, fail = 0
  for (const e of events.value) {
    if (e.done) continue
    if (e.status === 'ok')   pass++
    if (e.status === 'fail') fail++
  }
  return { pass, fail, done: pass + fail, total: PLAN.length }
})

// Elapsed time, ticking while running
const elapsedNow = ref(Date.now())
let tickHandle: number | null = null
function startTicker() {
  stopTicker()
  tickHandle = window.setInterval(() => { elapsedNow.value = Date.now() }, 250)
}
function stopTicker() {
  if (tickHandle !== null) { clearInterval(tickHandle); tickHandle = null }
}
const elapsedSec = computed(() => {
  if (!startedAt.value) return 0
  const end = finishedAt.value ?? elapsedNow.value
  return ((end - startedAt.value) / 1000).toFixed(1)
})

function run() {
  events.value = []
  startedAt.value = Date.now()
  finishedAt.value = null
  startTicker()
  sse.start('/api/system-check', {
    onMessage: (raw) => {
      try {
        const ev = JSON.parse(raw) as CheckEvent
        events.value.push(ev)
      } catch { /* ignore non-json */ }
    },
    onClose: () => {
      finishedAt.value = Date.now()
      stopTicker()
    },
  })
}

function stop() {
  sse.stop()
  finishedAt.value = Date.now()
  stopTicker()
}

async function copyAsMarkdown() {
  if (!events.value.length) return
  const lines: string[] = []
  lines.push(`## Hub System Check — ${new Date().toISOString().slice(0, 19).replace('T', ' ')}`)
  if (summaryEvent.value) {
    const passed = summaryEvent.value.passed ?? counts.value.pass
    const total  = summaryEvent.value.total ?? counts.value.done
    lines.push(`**Summary:** ${passed}/${total} passed · ${elapsedSec.value}s elapsed`)
  }
  lines.push('', '| Status | Check | Detail |', '| --- | --- | --- |')
  for (const e of checkEvents.value) {
    const icon = e.status === 'ok' ? '✅' : e.status === 'fail' ? '❌' : '⏳'
    lines.push(`| ${icon} | ${e.check || '—'} | ${(e.detail || '').replace(/\|/g, '\\|')} |`)
  }
  if (errorEvent.value) {
    lines.push('', `> ⚠ ${errorEvent.value.line}`)
  }
  try {
    await navigator.clipboard.writeText(lines.join('\n'))
    toast.show('📋 Copied report as Markdown', 'ok')
  } catch {
    toast.show('Copy failed — clipboard API blocked', 'err')
  }
}

// Find the per-check event for a planned step (so plan rows can show live status)
function statusFor(name: string): CheckEvent | undefined {
  return checkEvents.value.find((e) => e.check === name)
}

onUnmounted(() => {
  stopTicker()
  sse.stop()
})
</script>

<template>
  <div class="card">
    <div class="card-title" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
      <span>🩺 System Check</span>
      <span v-if="startedAt" class="elapsed">· {{ elapsedSec }}s</span>
      <span v-if="sse.connected.value" class="progress-text">{{ counts.done }}/{{ counts.total }}</span>

      <div style="margin-left:auto;display:flex;gap:6px">
        <button v-if="finished && events.length" class="btn btn-sm" @click="copyAsMarkdown" title="Copy report as Markdown">
          📋 Copy
        </button>
        <button v-if="sse.connected.value" class="btn btn-sm btn-danger" @click="stop">
          ⏹ Stop
        </button>
        <button v-else class="btn btn-primary" :disabled="sse.connected.value" @click="run">
          {{ events.length ? '↻ Re-run' : '▶ Run Check' }}
        </button>
      </div>
    </div>
    <p class="hint">
      ตรวจสุขภาพ Hub แบบ real-time — Python deps, Node, Hub config, Mock projects,
      TCM generation, Word generation, SMTP, Run history.
    </p>

    <!-- Plan checklist (always visible) -->
    <div class="checks">
      <div v-for="step in PLAN" :key="step.name" class="check"
           :class="{
             pass:    statusFor(step.name)?.status === 'ok',
             fail:    statusFor(step.name)?.status === 'fail',
             pending: !statusFor(step.name) && sse.connected.value,
             idle:    !statusFor(step.name) && !sse.connected.value,
           }">
        <div class="ico">
          <template v-if="statusFor(step.name)?.status === 'ok'">✅</template>
          <template v-else-if="statusFor(step.name)?.status === 'fail'">❌</template>
          <template v-else-if="sse.connected.value">⏳</template>
          <template v-else>○</template>
        </div>
        <div class="body">
          <div class="step">{{ step.name }}</div>
          <div class="detail">
            <template v-if="statusFor(step.name)?.detail">{{ statusFor(step.name)!.detail }}</template>
            <template v-else class="step-desc">{{ step.desc }}</template>
          </div>
        </div>
      </div>
    </div>

    <!-- Error banner from synthetic SSE error -->
    <div v-if="errorEvent" class="err-banner">
      <span style="font-size:18px">⚠️</span>
      <div>
        <div><b>Stream interrupted</b></div>
        <div style="font-size:11.5px">{{ errorEvent.line }}</div>
      </div>
    </div>

    <!-- Final summary -->
    <div v-if="summaryEvent && !errorEvent" class="summary"
         :class="{ allgood: counts.fail === 0 && counts.pass > 0, hasfail: counts.fail > 0 }">
      <strong v-if="counts.fail === 0 && counts.pass > 0">
        ✅ ทุก check ผ่านหมด ({{ summaryEvent.passed ?? counts.pass }}/{{ summaryEvent.total ?? counts.done }})
        · {{ elapsedSec }}s
      </strong>
      <strong v-else-if="counts.fail > 0">
        ⚠️ {{ counts.fail }} check ไม่ผ่าน ({{ summaryEvent.passed ?? counts.pass }}/{{ summaryEvent.total ?? counts.done }})
        · {{ elapsedSec }}s
      </strong>
    </div>

    <!-- Empty state when never run -->
    <div v-if="!events.length && !sse.connected.value" class="empty-hint">
      กด <b>▶ Run Check</b> เพื่อเริ่ม — ใช้เวลาประมาณ 30–60 วินาที (รวม mock TCM/Report generation)
    </div>
  </div>
</template>

<style scoped>
.hint { font-size: 12.5px; color: var(--muted); margin-bottom: 14px; }
.empty-hint { font-size: 12.5px; color: var(--muted); padding: 14px 4px 4px; border-top: 1px dashed var(--border-soft); margin-top: 14px; }

.elapsed       { font-size: 11.5px; color: var(--muted); font-family: "SF Mono", monospace; font-weight: 500; }
.progress-text { font-size: 11.5px; color: var(--primary); font-weight: 600; }

.checks { display: flex; flex-direction: column; gap: 6px; }
.check {
  display: flex;
  gap: 12px;
  padding: 9px 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-soft);
  background: var(--card);
  transition: background var(--duration-fast) var(--ease),
              border-color var(--duration-fast) var(--ease);
}
.check.pass    { background: var(--success-soft); border-color: rgba(48, 209, 88, 0.35); }
.check.fail    { background: var(--danger-soft);  border-color: rgba(255, 69, 58, 0.35); }
.check.pending { background: var(--warn-soft);    border-color: rgba(255, 159, 10, 0.35); }
.check.idle    { opacity: 0.65; }

.check .ico    { font-size: 16px; flex-shrink: 0; }
.check .step   { font-size: 13px; font-weight: 600; color: var(--text); }
.check .detail { font-size: 11.5px; color: var(--muted); margin-top: 2px; line-height: 1.45; word-break: break-word; }

.summary {
  padding: 12px 16px;
  border-radius: var(--radius-md);
  margin-top: 12px;
  font-size: 14px;
  border: 1px solid;
}
.summary.allgood {
  background: var(--success-soft);
  color: var(--success);
  border-color: rgba(48, 209, 88, 0.4);
}
.summary.hasfail {
  background: var(--danger-soft);
  color: var(--danger);
  border-color: rgba(255, 69, 58, 0.4);
}
[data-theme="dark"] .summary.allgood { color: var(--success); }

.err-banner {
  display: flex;
  gap: 10px;
  align-items: center;
  background: var(--danger-soft);
  color: var(--danger);
  border: 1px solid rgba(255, 69, 58, 0.35);
  border-radius: var(--radius-md);
  padding: 10px 14px;
  margin-top: 12px;
  font-size: 13px;
}
</style>
