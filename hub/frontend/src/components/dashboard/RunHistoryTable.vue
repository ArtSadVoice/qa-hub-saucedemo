<script setup lang="ts">
import { ref, computed, onMounted, watch, inject, type Ref } from 'vue'
import { apiCall } from '@/api/client'
import { useProjectStore } from '@/stores/projects'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'

interface Run {
  ts: string
  pass: number
  fail: number
  flaky?: number
  rc?: number
  tag?: string
  env?: string
  source?: string
}

const projects = useProjectStore()
const toast = useToast()
const { confirm } = useConfirm()
const refreshTick = inject<Ref<number>>('dashboardRefreshTick')

const runs = ref<Run[]>([])
const loading = ref(true)
const envFilter = ref<'all' | 'uat' | 'prod'>('all')
const showGhost = ref(false)

async function load() {
  if (!projects.current) return
  loading.value = true
  try {
    const q = envFilter.value !== 'all' ? `&env=${envFilter.value}` : ''
    const r = await apiCall<Run[]>(`/api/run/history?p=${projects.current}${q}`, { silent: true })
    runs.value = (r || []).slice().reverse()  // newest first
  } catch {
    runs.value = []
  } finally {
    loading.value = false
  }
}

const filteredRuns = computed(() => {
  if (showGhost.value) return runs.value
  return runs.value.filter((r) => (r.pass || 0) + (r.fail || 0) > 0)
})

const ghostCount = computed(() => runs.value.length - filteredRuns.value.length)

const passRate = (r: Run) => {
  const tot = (r.pass || 0) + (r.fail || 0)
  return tot ? Math.round((r.pass / tot) * 100) : null
}

function rateColor(p: number | null): string {
  if (p === null) return 'var(--muted)'
  if (p >= 90) return 'var(--success)'
  if (p >= 70) return 'var(--warn)'
  return 'var(--danger)'
}

async function deleteRow(r: Run) {
  const ok = await confirm({
    title: 'Delete this run entry?',
    desc: `<b>${r.ts}</b> · ${r.pass} pass / ${r.fail} fail · @${r.tag || 'all'} · ${r.env || 'uat'}`,
    icon: '🗑️', danger: true, okLabel: 'Delete',
  })
  if (!ok) return
  try {
    await apiCall('/api/run/history/delete', {
      body: { project_id: projects.current, ts: r.ts },
    })
    toast.show('Run entry deleted', 'ok')
    await load()
  } catch { /* apiCall toasted */ }
}

async function purge(mode: 'ghost' | 'failed' | 'all') {
  const labels = {
    ghost:  { label: 'ghost runs (pass=0 & fail=0)', danger: false },
    failed: { label: 'all failed runs',              danger: true  },
    all:    { label: 'ALL run history',              danger: true  },
  }[mode]
  const ok = await confirm({
    title: `Purge ${labels.label}?`,
    desc: 'This action cannot be undone.',
    icon: mode === 'all' ? '🚨' : '🗑️',
    danger: labels.danger,
    okLabel: 'Purge',
  })
  if (!ok) return
  try {
    const r = await apiCall<{ removed: number }>('/api/run/history/purge', {
      body: { project_id: projects.current, mode },
    })
    toast.show(`Purged ${r.removed} entries`, 'ok')
    await load()
  } catch { /* apiCall toasted */ }
}

onMounted(load)
watch(() => projects.current, load)
watch(envFilter, load)
if (refreshTick) watch(refreshTick, load)
</script>

<template>
  <div class="card">
    <div class="card-title" style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      <span>📜 Run History</span>
      <span class="count">{{ filteredRuns.length }} run{{ filteredRuns.length === 1 ? '' : 's' }}</span>

      <div class="env-bar">
        <button v-for="e in (['all','uat','prod'] as const)" :key="e"
                class="env-pill" :class="{ active: envFilter === e, prod: e === 'prod' }"
                @click="envFilter = e">
          {{ e === 'all' ? 'All' : e === 'uat' ? '🟢 UAT' : '🔴 Prod' }}
        </button>
      </div>

      <label class="ghost-toggle" v-if="ghostCount > 0">
        <input type="checkbox" v-model="showGhost">
        <span>Show {{ ghostCount }} ghost</span>
      </label>

      <div style="margin-left:auto;display:flex;gap:6px">
        <button class="btn btn-sm" @click="purge('ghost')" :disabled="!ghostCount" title="ลบ runs ที่ไม่มี pass/fail data">
          Purge ghost ({{ ghostCount }})
        </button>
        <button class="btn btn-sm btn-danger" @click="purge('all')" :disabled="!runs.length" title="ลบ run history ทั้งหมด">
          Purge all
        </button>
        <button class="btn btn-sm" @click="load">↻</button>
      </div>
    </div>

    <div v-if="loading" class="empty">Loading…</div>
    <div v-else-if="!filteredRuns.length" class="empty">
      <div style="font-size:32px;margin-bottom:8px">📭</div>
      <div>ยังไม่มี run history สำหรับ project นี้</div>
      <div style="font-size:12px;color:var(--muted);margin-top:4px">รัน Pipeline Stage 5 เพื่อสร้าง entry</div>
    </div>
    <div v-else class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Timestamp</th>
            <th style="width:60px">Env</th>
            <th style="width:90px">Scope</th>
            <th style="width:70px;text-align:right">Pass</th>
            <th style="width:70px;text-align:right">Fail</th>
            <th style="width:80px;text-align:right">Pass rate</th>
            <th style="width:80px">Source</th>
            <th style="width:40px"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in filteredRuns" :key="r.ts" :class="{ 'row-prod': r.env === 'prod', ghost: !((r.pass || 0) + (r.fail || 0)) }">
            <td><code class="ts">{{ r.ts }}</code></td>
            <td>
              <span class="env-pill-sm" :class="r.env || 'uat'">{{ r.env === 'prod' ? '🔴' : '🟢' }} {{ (r.env || 'uat').toUpperCase() }}</span>
            </td>
            <td>{{ r.tag ? `@${r.tag}` : 'all' }}</td>
            <td style="text-align:right;font-weight:600;color:var(--success)">{{ r.pass || 0 }}</td>
            <td style="text-align:right;font-weight:600;color:var(--danger)">{{ r.fail || 0 }}</td>
            <td style="text-align:right;font-weight:600" :style="{ color: rateColor(passRate(r)) }">
              {{ passRate(r) === null ? '—' : `${passRate(r)}%` }}
            </td>
            <td><code class="src">{{ r.source || 'manual' }}</code></td>
            <td>
              <button class="row-del" @click="deleteRow(r)" title="Delete this entry">×</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.count { font-size: 12px; color: var(--muted); font-weight: 400; }
.env-bar { display: flex; gap: 4px; }
.env-pill {
  padding: 2px 9px; border-radius: 14px; border: 1px solid var(--border);
  background: var(--bg); color: var(--muted); font-size: 11px; font-weight: 600; cursor: pointer;
}
.env-pill.active { background: var(--primary-soft); color: var(--primary-dk); border-color: rgba(0, 113, 227, 0.25); }
.env-pill.prod.active { background: var(--danger-soft); color: var(--danger); border-color: rgba(255, 59, 48, 0.3); }

.ghost-toggle { font-size: 11.5px; color: var(--muted); display: flex; gap: 4px; align-items: center; cursor: pointer; }
.ghost-toggle input { width: auto; margin: 0; }

.empty { text-align: center; padding: 40px; color: var(--muted); }
.table-wrap { max-height: 420px; overflow-y: auto; }
table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
th, td { padding: 7px 10px; border-bottom: 1px solid var(--border-soft); text-align: left; }
th { background: var(--table-header-bg); font-size: 10.5px; text-transform: uppercase; color: var(--muted); position: sticky; top: 0; }
.row-prod { background: rgba(255, 59, 48, 0.04); }
.row-prod:hover { background: rgba(255, 59, 48, 0.08); }
.ghost { opacity: 0.55; }
.ts { font-family: "SF Mono", monospace; font-size: 11px; }
.env-pill-sm { font-size: 10px; padding: 1px 6px; border-radius: 8px; font-weight: 700; }
.env-pill-sm.uat  { background: var(--success-soft); color: var(--success); }
.env-pill-sm.prod { background: var(--danger); color: white; }
.src { font-size: 10.5px; color: var(--muted); }
.row-del {
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  font-size: 16px;
  padding: 0 4px;
  border-radius: var(--radius-xs);
  transition: all var(--duration-fast) var(--ease);
}
.row-del:hover { color: var(--danger); background: var(--danger-soft); }
.btn-sm { padding: 5px 11px; font-size: 12px; }
</style>
