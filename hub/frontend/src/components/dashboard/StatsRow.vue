<script setup lang="ts">
import { ref, computed, onMounted, watch, inject, type Ref } from 'vue'
import { apiCall } from '@/api/client'
import { useProjectStore } from '@/stores/projects'
import { useBugsStore } from '@/stores/bugs'

const refreshTick = inject<Ref<number>>('dashboardRefreshTick')

interface Info {
  total_tc?: number
  totals?: { pass?: number; fail?: number; 'not start'?: number; 'in-progress'?: number; block?: number; cancel?: number }
  accuracy?: number       // pre-computed pass rate % from Excel
  shot_count?: number
  pw_last?: { total: number; pass: number; fail: number; pct?: number }
}

const projects = useProjectStore()
const bugs = useBugsStore()
const info = ref<Info>({})

async function load() {
  if (!projects.current) return
  try {
    info.value = await apiCall<Info>(`/api/info?p=${projects.current}`, { silent: true })
  } catch {
    info.value = {}
  }
}

onMounted(async () => {
  if (!projects.all.length) await projects.load()
  load()
})
watch(() => projects.current, load)
if (refreshTick) watch(refreshTick, load)

// API returns totals.pass/totals.fail (nested) for full-pipeline,
// pw_last.pass/pw_last.fail for playwright-only.
const passCount = computed<number | null>(() => {
  const i = info.value
  if (i.totals?.pass !== undefined) return i.totals.pass
  if (i.pw_last?.pass !== undefined) return i.pw_last.pass
  return null
})
const failCount = computed<number | null>(() => {
  const i = info.value
  if (i.totals?.fail !== undefined) return i.totals.fail
  if (i.pw_last?.fail !== undefined) return i.pw_last.fail
  return null
})

const passRate = computed<number | null>(() => {
  const i = info.value
  // Prefer pre-computed values from server
  if (typeof i.accuracy === 'number') return i.accuracy
  if (typeof i.pw_last?.pct === 'number') return i.pw_last.pct
  // Fallback: compute from raw counts
  const p = passCount.value, f = failCount.value
  if (p === null && f === null) return null
  const tot = (p || 0) + (f || 0)
  return tot ? Math.round((p! / tot) * 100) : null
})

const passRateColor = computed(() => {
  const r = passRate.value
  if (r === null) return 'var(--muted)'
  if (r >= 90) return 'var(--success)'
  if (r >= 70) return 'var(--warn)'
  return 'var(--danger)'
})
</script>

<template>
  <div class="row">
    <div class="stat">
      <div class="n">{{ info.total_tc ?? info.pw_last?.total ?? '—' }}</div>
      <div class="l">Tests</div>
    </div>
    <div class="stat ok">
      <div class="n">{{ passCount ?? '—' }}</div>
      <div class="l">Pass</div>
    </div>
    <div class="stat fail">
      <div class="n">{{ failCount ?? '—' }}</div>
      <div class="l">Fail</div>
    </div>
    <div class="stat">
      <div class="n" :style="{color: passRateColor}">
        {{ passRate ?? '—' }}{{ passRate !== null ? '%' : '' }}
      </div>
      <div class="l">Pass rate</div>
    </div>
    <div class="stat" :class="{ has: bugs.openCount > 0 }">
      <div class="n" :style="{color: bugs.openCount > 0 ? 'var(--danger)' : ''}">{{ bugs.openCount }}</div>
      <div class="l">Open bugs</div>
    </div>
    <div class="stat">
      <div class="n">{{ info.shot_count ?? '—' }}</div>
      <div class="l">Screenshots</div>
    </div>
  </div>
</template>

<style scoped>
.row { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-bottom: 14px; }
.stat {
  background: var(--card);
  border: 1px solid var(--border-soft);
  border-left: 4px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  text-align: center;
  transition: border-left-color var(--duration-fast) var(--ease);
  box-shadow: var(--shadow-sm);
}
.stat.ok   { border-left-color: var(--success); }
.stat.fail { border-left-color: var(--danger); }
.stat.has  { border-left-color: var(--danger); }
.stat .n { font-size: 26px; font-weight: 700; color: var(--text); letter-spacing: -0.02em; }
.stat .l { font-size: 11px; text-transform: uppercase; color: var(--muted); letter-spacing: .5px; font-weight: 600; }

/* Auto-fit: stays at 6 cols on wide, drops to fewer as space shrinks */
@media (max-width: 1280px) { .row { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 640px)  { .row { grid-template-columns: repeat(2, 1fr); } }
</style>
