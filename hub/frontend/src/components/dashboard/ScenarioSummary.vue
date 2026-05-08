<script setup lang="ts">
import { ref, computed, onMounted, watch, inject, type Ref } from 'vue'
import { apiCall } from '@/api/client'
import { useProjectStore } from '@/stores/projects'

const refreshTick = inject<Ref<number>>('dashboardRefreshTick')

interface Scenario {
  tsid?: string
  desc?: string
  pass?: number
  fail?: number
  block?: number
  not_start?: number
  cancel?: number
  total?: number
}

// /api/info actually returns ts_order + ts_data (see app.py read_excel_data),
// not a flat `scenarios` array. Earlier versions of this component looked
// for `r.scenarios || r.tcm` — neither key exists, so the table always
// rendered the empty-state "ไม่พบ TCM data" even when the project had a
// fully-populated xlsx.
interface ApiInfoResponse {
  ts_order?: string[]
  ts_data?: Record<string, { desc?: string; counts?: Record<string, number> }>
  scenarios?: Scenario[]   // legacy / future-compat — accept if backend ever ships it
  tcm?: Scenario[]         // legacy alias
}

const projects = useProjectStore()
const scenarios = ref<Scenario[]>([])
const loading = ref(true)
const envFilter = ref<'all' | 'uat' | 'prod'>('all')

function adaptInfoResponse(r: ApiInfoResponse): Scenario[] {
  // Prefer the live API shape — derive scenarios from ts_order + ts_data.
  if (r.ts_order && r.ts_data) {
    return r.ts_order.map((tsid) => {
      const node = r.ts_data?.[tsid]
      const counts = node?.counts || {}
      const get = (k: string) => Number(counts[k] || 0)
      const pass = get('pass')
      const fail = get('fail')
      const block = get('block')
      const not_start = get('not start')
      const cancel = get('cancel')
      const inProgress = get('in-progress')
      return {
        tsid,
        desc: node?.desc || '',
        pass, fail, block, not_start, cancel,
        total: pass + fail + block + not_start + cancel + inProgress,
      }
    })
  }
  // Fallback to legacy keys if backend ever ships them.
  return r.scenarios || r.tcm || []
}

async function load() {
  if (!projects.current) return
  loading.value = true
  try {
    const q = envFilter.value !== 'all' ? `&env=${envFilter.value}` : ''
    const r = await apiCall<ApiInfoResponse>(
      `/api/info?p=${projects.current}${q}`,
      { silent: true }
    )
    scenarios.value = adaptInfoResponse(r)
  } catch {
    scenarios.value = []
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

const totals = computed(() => {
  const t = { pass: 0, fail: 0, block: 0, not_start: 0, cancel: 0, total: 0 }
  scenarios.value.forEach((s) => {
    t.pass += s.pass || 0
    t.fail += s.fail || 0
    t.block += s.block || 0
    t.not_start += s.not_start || 0
    t.cancel += s.cancel || 0
    t.total += s.total || (s.pass || 0) + (s.fail || 0) + (s.block || 0) + (s.not_start || 0) + (s.cancel || 0)
  })
  return t
})

const exportUrl = computed(() => {
  const q = envFilter.value !== 'all' ? `&env=${envFilter.value}` : ''
  return `/api/info/export-excel?p=${projects.current}${q}`
})
</script>

<template>
  <div class="card">
    <div class="card-title" style="display:flex;align-items:center;gap:10px">
      📋 Test Scenario Summary
      <div class="env-bar">
        <button v-for="e in (['all','uat','prod'] as const)" :key="e"
                class="env-pill"
                :class="{ active: envFilter === e, prod: e === 'prod' }"
                @click="envFilter = e">
          {{ e === 'all' ? 'All' : e === 'uat' ? '🟢 UAT' : '🔴 Prod' }}
        </button>
      </div>
      <a v-if="scenarios.length" :href="exportUrl" target="_blank"
         class="btn btn-sm" style="margin-left:auto;text-decoration:none">📥 Export Excel</a>
      <button v-else class="btn btn-sm" disabled style="margin-left:auto" title="No data to export">📥 Export Excel</button>
    </div>

    <div v-if="loading" class="empty">Loading…</div>
    <div v-else-if="!scenarios.length" class="empty">
      ไม่พบ TCM data — Upload Excel + run Stage 2 ก่อน
    </div>
    <table v-else class="table-stack">
      <thead>
        <tr>
          <th>TSID</th>
          <th>Description</th>
          <th style="text-align:right">Pass</th>
          <th style="text-align:right">Fail</th>
          <th style="text-align:right">Block</th>
          <th style="text-align:right">Not Start</th>
          <th style="text-align:right">Cancel</th>
          <th style="text-align:right">Total</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(s, i) in scenarios" :key="i">
          <td data-label="TSID"><b>{{ s.tsid || `TS_${String(i + 1).padStart(3, '0')}` }}</b></td>
          <td data-label="Description" class="desc-cell" :title="s.desc || ''">{{ s.desc || '—' }}</td>
          <td data-label="Pass" style="text-align:right;color:var(--success)"><b>{{ s.pass ?? 0 }}</b></td>
          <td data-label="Fail" style="text-align:right;color:var(--danger)"><b>{{ s.fail ?? 0 }}</b></td>
          <td data-label="Block" style="text-align:right;color:var(--warn)">{{ s.block ?? 0 }}</td>
          <td data-label="Not Start" style="text-align:right;color:var(--muted)">{{ s.not_start ?? 0 }}</td>
          <td data-label="Cancel" style="text-align:right;color:var(--muted)">{{ s.cancel ?? 0 }}</td>
          <td data-label="Total" style="text-align:right">{{ s.total ?? ((s.pass || 0) + (s.fail || 0) + (s.block || 0) + (s.not_start || 0) + (s.cancel || 0)) }}</td>
        </tr>
      </tbody>
      <tfoot>
        <tr>
          <th>Total</th>
          <th></th>
          <th style="text-align:right;color:var(--success)">{{ totals.pass }}</th>
          <th style="text-align:right;color:var(--danger)">{{ totals.fail }}</th>
          <th style="text-align:right;color:var(--warn)">{{ totals.block }}</th>
          <th style="text-align:right;color:var(--muted)">{{ totals.not_start }}</th>
          <th style="text-align:right;color:var(--muted)">{{ totals.cancel }}</th>
          <th style="text-align:right">{{ totals.total }}</th>
        </tr>
      </tfoot>
    </table>
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
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 8px 10px; border-bottom: 1px solid var(--border); text-align: left; }
th { background: var(--table-header-bg); font-size: 11px; text-transform: uppercase; color: var(--muted); }
tfoot th { background: var(--bg); font-size: 12px; }
.btn-sm { padding: 4px 10px; font-size: 12px; }
/* Description column: let it wrap to multiple lines so the table never
   exceeds its card. With white-space:nowrap + max-width:360px the column
   used the full text width for layout (max-width on td is a hint that
   table-layout:auto can ignore), pushing the table past the card on
   tablet-and-narrow-desktop viewports (641-1100ish). */
.desc-cell {
  max-width: 360px;
  word-break: break-word;
  overflow-wrap: anywhere;
  color: var(--text-secondary, var(--text));
}
/* Belt-and-suspenders: enforce the card boundary even if a future cell
   forgets to wrap. Horizontal scroll within card beats overflow into the
   next card. */
table {
  table-layout: auto;
  max-width: 100%;
}
.card { overflow-x: auto; }
@media (max-width: 640px) {
  /* In stacked-card mode the description gets its own row */
  .desc-cell {
    max-width: 100%;
    text-align: right;
  }
}
</style>
