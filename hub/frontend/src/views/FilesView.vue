<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { apiCall } from '@/api/client'
import { useProjectStore } from '@/stores/projects'
import { useToast } from '@/composables/useToast'
import { copyTextWithFallback } from '@/utils/clipboard'

interface Props {
  /** which folder to list — 'input' / 'output' / 'screenshots' / 'requirements' / 'figma' */
  kind: 'input' | 'output' | 'screenshots' | 'requirements' | 'figma'
  title: string
  icon: string
  /** path to download endpoint, with project ID injected */
  downloadHref?: (file: string, pid: string) => string
}

const toast = useToast()

async function copyPath() {
  if (!projects.current) return
  // Resolve path first; clipboard write is a separate failure mode.
  // (See @/utils/clipboard for the why behind the fallback.)
  let path = ''
  try {
    const r = await apiCall<{ path: string }>(
      `/api/path/${props.kind}?p=${projects.current}`,
      { silent: true }
    )
    path = r.path || ''
  } catch {
    toast.show(`Couldn't resolve ${props.kind}/ path`, 'err')
    return
  }
  if (!path) {
    toast.show(`No path returned for ${props.kind}/`, 'err')
    return
  }
  const ok = await copyTextWithFallback(path)
  if (ok) {
    toast.show(`📋 คัดลอก path แล้ว — วางใน Win+R หรือ Explorer address bar:\n${path}`, 'ok')
  } else {
    toast.show(`Clipboard ใช้ไม่ได้ — คัดลอก path นี้เอง:\n${path}`, 'warn', 12000)
  }
}

const props = defineProps<Props>()
const projects = useProjectStore()

interface FileEntry {
  name: string
  size_kb?: number       // server returns KB (rounded to 0.1)
  modified?: string      // pre-formatted "27 Apr 2026 14:30"
  ext?: string
}
const files = ref<FileEntry[]>([])
const loading = ref(true)

async function load() {
  if (!projects.current) return
  loading.value = true
  try {
    const r = await apiCall<{ files: FileEntry[] } | FileEntry[]>(
      `/api/${props.kind}/list?p=${projects.current}`,
      { silent: true }
    )
    files.value = Array.isArray(r) ? r : (r as { files: FileEntry[] }).files || []
  } catch {
    files.value = []
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (!projects.all.length) await projects.load()
  load()
})
watch(() => projects.current, load)

// API returns size in KB (already rounded). Convert to human-friendly bytes/KB/MB.
const fmtSizeKB = (kb?: number): string => {
  if (kb === undefined || kb === null) return ''
  if (kb < 1) return `${Math.round(kb * 1024)} B`
  if (kb < 1024) return `${kb.toFixed(1)} KB`
  return `${(kb / 1024).toFixed(2)} MB`
}

const totalSizeKB = computed(() => files.value.reduce((sum, f) => sum + (f.size_kb || 0), 0))
</script>

<template>
  <div class="card">
    <div class="card-title" style="display:flex;align-items:center;gap:8px">
      {{ icon }} {{ title }}
      <span style="font-size:12px;color:var(--muted);font-weight:400">
        {{ files.length }} file{{ files.length === 1 ? '' : 's' }}
        <span v-if="totalSizeKB">· {{ fmtSizeKB(totalSizeKB) }} total</span>
      </span>
      <div style="margin-left:auto;display:flex;gap:6px">
        <button class="btn btn-sm" @click="copyPath" title="คัดลอก absolute path ไป clipboard — วางใน Win+R หรือ Explorer address bar">📋 Copy path</button>
        <button class="btn btn-sm" @click="load">↻ Refresh</button>
      </div>
    </div>

    <div v-if="loading" class="empty">Loading…</div>
    <div v-else-if="!files.length" class="empty">
      ยังไม่มีไฟล์ใน {{ kind }}/ — สำหรับ project <b>{{ projects.currentMeta?.name || '—' }}</b>
    </div>
    <table v-else>
      <thead>
        <tr>
          <th>Name</th>
          <th style="width:100px;text-align:right">Size</th>
          <th style="width:160px">Modified</th>
          <th v-if="downloadHref" style="width:90px"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="f in files" :key="f.name">
          <td><b>{{ f.name }}</b></td>
          <td style="text-align:right;font-family:monospace;font-size:12px;color:var(--muted)">{{ fmtSizeKB(f.size_kb) }}</td>
          <td style="font-family:monospace;font-size:11.5px;color:var(--muted)">{{ f.modified || '—' }}</td>
          <td v-if="downloadHref">
            <a :href="downloadHref(f.name, projects.current)" class="btn btn-sm" target="_blank">⬇ Download</a>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.empty { text-align: center; padding: 30px; color: var(--muted); font-style: italic; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 8px 10px; border-bottom: 1px solid var(--bg); text-align: left; }
th { background: var(--bg); font-size: 11px; text-transform: uppercase; color: var(--muted); }
.btn-sm { padding: 4px 10px; font-size: 12px; text-decoration: none; display: inline-block; }
</style>
