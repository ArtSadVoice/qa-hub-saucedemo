<script setup lang="ts">
import { ref, onMounted, watch, inject, computed, type Ref } from 'vue'
import { apiCall } from '@/api/client'
import { useProjectStore } from '@/stores/projects'

const refreshTick = inject<Ref<number>>('dashboardRefreshTick')

// Field order mirrors the legacy dashboard (static/app.js around the
// proj-table render) so a user switching between v1 and v2 sees the
// same row layout. Keys are the exact strings written in the xlsx
// PROJECT_INFO sheet — case- and whitespace-sensitive.
const PROJECT_FIELDS = [
  'Project Code',
  'Project Name',
  'Topic',
  'Customer',
  'Prepared By',
  'Prepared Date',
  'Sprint / Version',
] as const

interface ApiInfoResponse {
  project?: Record<string, string>
  input_file?: string
}

const projects = useProjectStore()
const projectInfo = ref<Record<string, string>>({})
const inputFile = ref<string>('')
const loading = ref(true)

async function load() {
  if (!projects.current) return
  loading.value = true
  try {
    const r = await apiCall<ApiInfoResponse>(
      `/api/info?p=${projects.current}`,
      { silent: true }
    )
    projectInfo.value = r.project || {}
    inputFile.value = r.input_file || ''
  } catch {
    projectInfo.value = {}
    inputFile.value = ''
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (!projects.all.length) await projects.load()
  load()
})
watch(() => projects.current, load)
if (refreshTick) watch(refreshTick, load)

// Show empty state only when truly empty — a project that's just been
// registered but has no xlsx yet returns project={}.
const hasAnyValue = computed(() =>
  PROJECT_FIELDS.some((f) => (projectInfo.value[f] || '').trim() !== '')
)
</script>

<template>
  <div class="card">
    <div class="card-title" style="display:flex;align-items:center;gap:10px">
      📑 Project Information
      <span v-if="inputFile" class="src-pill" :title="`Source: input/${inputFile}`">
        from <code>{{ inputFile }}</code>
      </span>
    </div>

    <div v-if="loading" class="empty">Loading…</div>
    <div v-else-if="!hasAnyValue" class="empty">
      ไม่พบ Project Info — Upload Excel ที่มี sheet PROJECT_INFO แล้ว refresh
    </div>
    <table v-else class="info-table">
      <tbody>
        <tr v-for="f in PROJECT_FIELDS" :key="f">
          <td class="lbl">{{ f }}</td>
          <td class="val">{{ projectInfo[f] || '—' }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.empty { text-align: center; padding: 30px; color: var(--muted); font-style: italic; }
.src-pill {
  font-size: 11px;
  color: var(--muted);
  margin-left: auto;
}
.src-pill code {
  font-family: "SF Mono", monospace;
  background: var(--bg);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-soft);
}
.info-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.info-table td {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
}
.info-table tr:last-child td { border-bottom: none; }
.info-table .lbl {
  width: 180px;
  font-weight: 600;
  color: var(--muted);
  font-size: 12px;
}
.info-table .val {
  font-size: 13px;
  color: var(--text);
}
</style>
