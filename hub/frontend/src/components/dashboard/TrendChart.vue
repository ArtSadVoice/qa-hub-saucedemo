<script setup lang="ts">
import { ref, computed, onMounted, watch, inject, type Ref } from 'vue'
import { apiCall } from '@/api/client'
import { useProjectStore } from '@/stores/projects'

const refreshTick = inject<Ref<number>>('dashboardRefreshTick')

interface TrendPoint {
  ts: string
  pass: number
  fail: number
  total?: number
  pass_pct?: number
  tag?: string
}

const projects = useProjectStore()
const points = ref<TrendPoint[]>([])
const loading = ref(true)
const envFilter = ref<'all' | 'uat' | 'prod'>('all')

async function load() {
  if (!projects.current) return
  loading.value = true
  try {
    const q = envFilter.value !== 'all' ? `&env=${envFilter.value}` : ''
    const r = await apiCall<{ points?: TrendPoint[] } | TrendPoint[]>(
      `/api/run/trend?p=${projects.current}${q}`,
      { silent: true }
    )
    points.value = Array.isArray(r) ? r : (r as { points: TrendPoint[] }).points || []
  } catch {
    points.value = []
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (!projects.all.length) await projects.load()
  load()
})
watch(() => projects.current, load)
watch(envFilter, load)
if (refreshTick) watch(refreshTick, load)

// Compute pass-rate per point
const data = computed(() =>
  points.value.map((p) => {
    const total = (p.pass || 0) + (p.fail || 0)
    return {
      ...p,
      total,
      pct: total > 0 ? Math.round((p.pass / total) * 100) : null,
    }
  })
)

// Per-tag legend colors
const TAG_COLORS: Record<string, string> = {
  '':           '#0071E3',
  'smoke':      '#34C759',
  'e2e':        '#FF9F0A',
  'regression': '#AF52DE',
  'visual':     '#FF2D55',
}
const tagsInWindow = computed(() => {
  const seen = new Set<string>()
  for (const d of data.value) seen.add(d.tag || '')
  return [...seen]
})

const stats = computed(() => {
  if (!data.value.length) return null
  const passRates = data.value.map((d) => d.pct).filter((v): v is number => v !== null)
  const avg = passRates.length ? Math.round(passRates.reduce((a, b) => a + b, 0) / passRates.length) : 0
  const last = data.value[data.value.length - 1]
  return {
    runs: data.value.length,
    avg,
    latest: last.pct,
    latestTag: last.tag,
  }
})

// SVG path generation
const W = 600
const H = 180
const PAD = 28

const linePath = computed(() => {
  if (!data.value.length) return ''
  const pts = data.value.filter((d) => d.pct !== null)
  if (!pts.length) return ''
  const stepX = (W - PAD * 2) / Math.max(1, pts.length - 1)
  const coords = pts.map((d, i) => {
    const x = PAD + i * stepX
    const y = PAD + (1 - (d.pct! / 100)) * (H - PAD * 2)
    return [x, y] as [number, number]
  })
  // Smooth bezier
  let path = `M ${coords[0][0]},${coords[0][1]}`
  for (let i = 1; i < coords.length; i++) {
    const [px, py] = coords[i - 1]
    const [cx, cy] = coords[i]
    const midX = (px + cx) / 2
    path += ` C ${midX},${py} ${midX},${cy} ${cx},${cy}`
  }
  return path
})

const areaPath = computed(() => {
  if (!linePath.value) return ''
  return `${linePath.value} L ${W - PAD},${H - PAD} L ${PAD},${H - PAD} Z`
})

// Color line by latest pass rate
const lineColor = computed(() => {
  const last = stats.value?.latest
  if (last === undefined || last === null) return 'var(--muted)'
  if (last >= 90) return 'var(--success)'
  if (last >= 70) return 'var(--warn)'
  return 'var(--danger)'
})

// Hover tooltip
const hoverIdx = ref<number | null>(null)
const hoverPos = computed(() => {
  if (hoverIdx.value === null || !data.value.length) return null
  const stepX = (W - PAD * 2) / Math.max(1, data.value.length - 1)
  const x = PAD + hoverIdx.value * stepX
  const d = data.value[hoverIdx.value]
  if (!d) return null
  return { x, d }
})

function onMouseMove(e: MouseEvent) {
  if (!data.value.length) return
  const svg = (e.currentTarget as SVGElement).getBoundingClientRect()
  const ratio = (e.clientX - svg.left) / svg.width
  const x = ratio * W
  if (x < PAD || x > W - PAD) { hoverIdx.value = null; return }
  const stepX = (W - PAD * 2) / Math.max(1, data.value.length - 1)
  hoverIdx.value = Math.round((x - PAD) / stepX)
}

function onMouseLeave() { hoverIdx.value = null }
</script>

<template>
  <div class="card">
    <div class="card-title" style="display:flex;align-items:center;gap:10px">
      📊 Test Run Trend
      <div class="env-bar">
        <button v-for="e in (['all','uat','prod'] as const)" :key="e"
                class="env-pill"
                :class="{ active: envFilter === e, prod: e === 'prod' }"
                @click="envFilter = e">
          {{ e === 'all' ? 'All' : e === 'uat' ? '🟢 UAT' : '🔴 Prod' }}
        </button>
      </div>
      <button class="btn btn-sm" @click="load" style="margin-left:auto">↻</button>
    </div>

    <div v-if="stats" class="trend-stats">
      <div class="stat"><div class="n">{{ stats.runs }}</div><div class="l">Runs</div></div>
      <div class="stat"><div class="n">{{ stats.avg }}%</div><div class="l">Avg pass rate</div></div>
      <div class="stat"><div class="n" :style="{color: lineColor}">{{ stats.latest ?? '—' }}{{ stats.latest !== null ? '%' : '' }}</div><div class="l">Latest</div></div>
      <div class="stat"><div class="n">{{ stats.latestTag || 'all' }}</div><div class="l">Last scope</div></div>
    </div>

    <div v-if="loading" class="empty">Loading…</div>
    <div v-else-if="!data.length" class="empty">ยังไม่มี run history สำหรับ project นี้</div>
    <div v-else class="chart-wrap">
      <svg :viewBox="`0 0 ${W} ${H}`" preserveAspectRatio="xMidYMid meet"
           @mousemove="onMouseMove" @mouseleave="onMouseLeave">
        <!-- Gradient -->
        <defs>
          <linearGradient :id="'trend-grad-' + envFilter" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" :stop-color="lineColor" stop-opacity="0.25" />
            <stop offset="100%" :stop-color="lineColor" stop-opacity="0" />
          </linearGradient>
        </defs>
        <!-- Grid -->
        <line v-for="y in [0, 25, 50, 75, 100]" :key="y"
              :x1="PAD" :x2="W - PAD"
              :y1="PAD + (1 - y / 100) * (H - PAD * 2)"
              :y2="PAD + (1 - y / 100) * (H - PAD * 2)"
              stroke="var(--border)" stroke-dasharray="2,3" stroke-width="0.5" />
        <text v-for="y in [0, 50, 100]" :key="y + 'l'"
              :x="PAD - 4" :y="PAD + (1 - y / 100) * (H - PAD * 2) + 4"
              text-anchor="end" font-size="10" fill="var(--muted)">{{ y }}</text>
        <!-- Area fill -->
        <path :d="areaPath" :fill="`url(#trend-grad-${envFilter})`" />
        <!-- Line -->
        <path :d="linePath" :stroke="lineColor" stroke-width="2.5" fill="none" stroke-linejoin="round" />
        <!-- Points -->
        <g v-if="data.length">
          <circle v-for="(d, i) in data.filter(x => x.pct !== null)" :key="i"
                  :cx="PAD + i * (W - PAD * 2) / Math.max(1, data.length - 1)"
                  :cy="PAD + (1 - (d.pct! / 100)) * (H - PAD * 2)"
                  r="3" :fill="lineColor" :stroke="'var(--card)'" stroke-width="1.5" />
        </g>
        <!-- Hover indicator -->
        <line v-if="hoverPos" :x1="hoverPos.x" :x2="hoverPos.x" :y1="PAD" :y2="H - PAD"
              stroke="var(--muted)" stroke-width="0.8" stroke-dasharray="3,3" />
      </svg>
      <div v-if="hoverPos" class="tooltip" :style="{ left: (hoverPos.x / W * 100) + '%' }">
        <div><b>{{ hoverPos.d.ts }}</b></div>
        <div>Pass: {{ hoverPos.d.pass }} · Fail: {{ hoverPos.d.fail }}</div>
        <div v-if="hoverPos.d.pct !== null"><b>{{ hoverPos.d.pct }}%</b> pass rate</div>
        <div v-if="hoverPos.d.tag" style="font-size:11px;color:var(--muted)">@{{ hoverPos.d.tag }}</div>
      </div>
    </div>
    <!-- Tag legend -->
    <div v-if="tagsInWindow.length > 1" class="legend">
      <span v-for="t in tagsInWindow" :key="t" class="legend-item">
        <span class="dot" :style="{ background: TAG_COLORS[t] || TAG_COLORS[''] }"></span>
        {{ t || 'all' }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.empty { text-align: center; padding: 30px; color: var(--muted); font-style: italic; }
.env-bar { display: flex; gap: 4px; }
.env-pill {
  padding: 2px 9px; border-radius: 14px; border: 1px solid var(--border);
  background: var(--bg); color: var(--muted); font-size: 11px; font-weight: 600;
  cursor: pointer;
}
.env-pill.active { background: #E3F2FD; color: var(--primary); border-color: var(--primary-soft); }  /* stylelint-disable-line color-no-hex */
.env-pill.prod.active { background: #FFEBEE; color: var(--danger); border-color: var(--danger-soft); }  /* stylelint-disable-line color-no-hex */
.trend-stats { display: flex; gap: 12px; margin: 10px 0 14px; flex-wrap: wrap; }
.trend-stats .stat {
  background: var(--bg); border: 1px solid var(--border); border-radius: 8px;
  padding: 6px 12px; min-width: 100px;
}
.trend-stats .n { font-size: 18px; font-weight: 700; }
.trend-stats .l { font-size: 10.5px; color: var(--muted); text-transform: uppercase; letter-spacing: .5px; }
.chart-wrap { position: relative; max-height: 280px; }
.chart-wrap svg { width: 100%; height: auto; max-height: 280px; display: block; }
.tooltip {
  position: absolute;
  bottom: 100%;
  transform: translateX(-50%);
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 11.5px;
  white-space: nowrap;
  box-shadow: 0 4px 12px rgba(0,0,0,.1);
  pointer-events: none;
}
.btn-sm { padding: 4px 10px; font-size: 12px; }
.legend {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border-soft);
  font-size: 11.5px;
  color: var(--muted);
}
.legend-item { display: inline-flex; align-items: center; gap: 5px; }
.legend-item .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
</style>
