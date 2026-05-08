<script setup lang="ts">
import { computed } from 'vue'
import type { Bug, Severity, BugStatus } from '@/api/types'

const props = defineProps<{ bugs: Bug[] }>()

const SEVS: Severity[] = ['Critical', 'High', 'Medium', 'Low']
const STATUSES: BugStatus[] = ['Open', 'Fixed', 'Closed']

const sevStats = computed(() => SEVS.map((s) => ({
  s,
  open:   props.bugs.filter((b) => b.severity === s && b.status === 'Open').length,
  total:  props.bugs.filter((b) => b.severity === s).length,
})))

const statusStats = computed(() => STATUSES.map((st) => ({
  st,
  count: props.bugs.filter((b) => b.status === st).length,
})))

function ageDays(b: Bug): number | null {
  if (!b.created_at) return null
  const t = Date.parse(b.created_at.replace(' ', 'T'))
  return isNaN(t) ? null : Math.floor((Date.now() - t) / 86400000)
}

const ageBuckets = computed(() => {
  const open = props.bugs.filter((b) => b.status === 'Open')
  return [
    { label: '< 7d',  range: '0–6 days',   count: open.filter((b) => { const a = ageDays(b); return a !== null && a < 7 }).length,                color: 'var(--success)' },
    { label: '7–14d', range: '7–13 days',  count: open.filter((b) => { const a = ageDays(b); return a !== null && a >= 7 && a < 14 }).length,    color: 'var(--warn)' },
    { label: '≥ 14d', range: '14+ days',   count: open.filter((b) => { const a = ageDays(b); return a !== null && a >= 14 }).length,             color: 'var(--danger)' },
  ]
})

const total = computed(() => props.bugs.length)
const totalOpen = computed(() => props.bugs.filter((b) => b.status === 'Open').length)

const sevColor = (s: Severity) => ({
  Critical: 'var(--danger)',
  High:     'var(--danger)',
  Medium:   'var(--warn)',
  Low:      'var(--success)',
}[s])

const sevPct = (s: Severity) => total.value
  ? Math.round((props.bugs.filter((b) => b.severity === s).length / total.value) * 100)
  : 0
</script>

<template>
  <div class="card metrics" v-if="bugs.length">
    <div class="card-title">📊 Bug Metrics</div>

    <!-- Top stats row -->
    <div class="top-row">
      <div class="big-stat">
        <div class="n">{{ total }}</div>
        <div class="l">Total bugs</div>
      </div>
      <div class="big-stat" :class="{ alert: totalOpen > 0 }">
        <div class="n">{{ totalOpen }}</div>
        <div class="l">Open</div>
      </div>
      <div class="big-stat">
        <div class="n">{{ statusStats[1].count }}</div>
        <div class="l">Fixed</div>
      </div>
      <div class="big-stat">
        <div class="n">{{ statusStats[2].count }}</div>
        <div class="l">Closed</div>
      </div>
    </div>

    <!-- Severity distribution bar -->
    <div class="section">
      <div class="section-title">Severity distribution (all bugs)</div>
      <div class="stack-bar">
        <div v-for="s in SEVS" :key="s" class="seg"
             :style="{ width: sevPct(s) + '%', background: sevColor(s) }"
             :title="`${s}: ${sevPct(s)}% (${bugs.filter((b) => b.severity === s).length} bugs)`">
          <span v-if="sevPct(s) >= 8">{{ sevPct(s) }}%</span>
        </div>
      </div>
      <div class="legend">
        <span v-for="(s, i) in SEVS" :key="i" class="legend-item">
          <span class="dot" :style="{ background: sevColor(s) }"></span>
          {{ s }} <b>({{ bugs.filter((b) => b.severity === s).length }})</b>
        </span>
      </div>
    </div>

    <!-- Aging buckets — Open bugs only -->
    <div class="section" v-if="totalOpen > 0">
      <div class="section-title">Aging (Open bugs only)</div>
      <div class="age-row">
        <div v-for="b in ageBuckets" :key="b.label" class="age-bucket">
          <div class="age-n" :style="{ color: b.color }">{{ b.count }}</div>
          <div class="age-l">{{ b.label }}</div>
          <div class="age-r">{{ b.range }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.metrics .card-title { margin-bottom: var(--space-4); }

.top-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: var(--space-5);
}
.big-stat {
  background: var(--bg);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  padding: 14px;
  text-align: center;
}
.big-stat.alert { background: var(--danger-soft); border-color: rgba(255, 59, 48, 0.25); }
.big-stat .n { font-size: 28px; font-weight: 700; letter-spacing: -0.02em; }
.big-stat.alert .n { color: var(--danger); }
.big-stat .l { font-size: 11px; text-transform: uppercase; color: var(--muted); letter-spacing: 0.5px; font-weight: 600; }

.section { margin-top: var(--space-4); }
.section-title {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--muted);
  margin-bottom: 8px;
}
.stack-bar {
  display: flex;
  height: 22px;
  border-radius: 11px;
  overflow: hidden;
  background: var(--bg);
  border: 1px solid var(--border-soft);
}
.seg {
  height: 100%;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700; color: white;
  transition: width var(--duration-slow) var(--ease);
  min-width: 0;
}
.legend {
  display: flex; gap: 16px; flex-wrap: wrap;
  margin-top: 10px;
  font-size: 12px; color: var(--text-secondary);
}
.legend-item { display: inline-flex; align-items: center; gap: 6px; }
.legend-item .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }

.age-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.age-bucket {
  background: var(--card);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  padding: 12px;
  text-align: center;
}
.age-n { font-size: 24px; font-weight: 700; letter-spacing: -0.02em; }
.age-l { font-size: 12px; font-weight: 600; color: var(--text); margin-top: 2px; }
.age-r { font-size: 10.5px; color: var(--muted); margin-top: 1px; }

@media (max-width: 700px) {
  .top-row { grid-template-columns: repeat(2, 1fr); }
}
</style>
