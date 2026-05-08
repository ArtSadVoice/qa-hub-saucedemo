<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { apiCall } from '@/api/client'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { useProjectStore } from '@/stores/projects'

interface BackupEntry {
  name: string
  size_kb: number
  modified: string
}
interface BackupListResponse {
  backups: BackupEntry[]
  keep_days: number
}

const toast = useToast()
const { confirm } = useConfirm()
const projects = useProjectStore()

const fileInput = ref<HTMLInputElement | null>(null)
const importing = ref(false)
const backups = ref<BackupEntry[]>([])
const keepDays = ref(30)
const loadingList = ref(false)
const triggering = ref(false)

async function loadBackupList() {
  loadingList.value = true
  try {
    const r = await apiCall<BackupListResponse>('/api/config/backup/list', { silent: true })
    backups.value = r.backups
    keepDays.value = r.keep_days
  } catch {
    backups.value = []
  } finally {
    loadingList.value = false
  }
}

function exportConfig() {
  window.location.href = '/api/config/export'
  toast.show('📥 Downloading config.json…', 'ok')
}

function pickFile() {
  fileInput.value?.click()
}

async function onFileChosen(e: Event) {
  const input = e.target as HTMLInputElement
  const f = input.files?.[0]
  input.value = ''
  if (!f) return

  const ok = await confirm({
    title: 'Import config.json?',
    desc: `จะแทนที่ project list และ settings ปัจจุบันทั้งหมดด้วยไฟล์ "${f.name}".\nแนะนำให้สร้าง snapshot ปัจจุบันก่อน เผื่อ rollback`,
    danger: true,
    okLabel: 'Import & Replace',
  })
  if (!ok) return

  importing.value = true
  try {
    const fd = new FormData()
    fd.append('file', f)
    const r = await fetch('/api/config/import', { method: 'POST', body: fd })
    const j = await r.json()
    if (!r.ok || !j.ok) {
      toast.show(`Import failed: ${j.error || 'unknown error'}`, 'err')
      return
    }
    toast.show(`✓ Imported ${j.count} project(s) — reloading`, 'ok')
    await projects.load()
    setTimeout(() => window.location.reload(), 800)
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    toast.show(`Import failed: ${msg}`, 'err')
  } finally {
    importing.value = false
  }
}

async function snapshotNow() {
  triggering.value = true
  try {
    const r = await apiCall<{ ok: boolean; name: string }>('/api/config/backup/run', { body: {} })
    toast.show(`📦 Snapshot saved: ${r.name}`, 'ok')
    await loadBackupList()
  } catch { /* apiCall toasted */ } finally {
    triggering.value = false
  }
}

async function restoreBackup(b: BackupEntry) {
  const ok = await confirm({
    title: `Restore from ${b.name}?`,
    desc: `จะแทนที่ config ปัจจุบันด้วย snapshot นี้ (${b.modified}).\nระบบจะ reload หลัง restore สำเร็จ.`,
    danger: true,
    okLabel: 'Restore',
  })
  if (!ok) return
  try {
    const r = await apiCall<{ ok: boolean; restored_from: string; projects: number }>(
      '/api/config/backup/restore', { body: { name: b.name } }
    )
    toast.show(`✓ Restored ${r.projects} project(s) from ${r.restored_from}`, 'ok')
    await projects.load()
    setTimeout(() => window.location.reload(), 800)
  } catch { /* apiCall toasted */ }
}

onMounted(loadBackupList)
</script>

<template>
  <div class="card">
    <div class="card-title">💾 Backup &amp; Restore</div>
    <p class="hint">
      Export <code>config.json</code> สำหรับ backup project list, branding, email, notifications, AI settings
      ทั้งหมด — Import จะแทนที่ config ปัจจุบันด้วยไฟล์ที่อัปโหลด.
      Hub บันทึก snapshot ราย<b>วัน</b>อัตโนมัติ (เก็บ {{ keepDays }} วัน) ใน <code>config_backups/</code>.
    </p>

    <div class="actions">
      <button class="btn btn-primary" @click="exportConfig">
        📥 Export config.json
      </button>
      <button class="btn" :disabled="importing" @click="pickFile">
        {{ importing ? '⏳ Importing…' : '📤 Import config.json' }}
      </button>
      <button class="btn" :disabled="triggering" @click="snapshotNow"
              title="สร้าง snapshot ทันที (เช่น ก่อน import ใหญ่)">
        {{ triggering ? '⏳' : '📸' }} Snapshot now
      </button>
      <input ref="fileInput" type="file" accept=".json,application/json" @change="onFileChosen" hidden />
    </div>

    <div class="warn-banner">
      <b>⚠ Tip:</b> Import จะ overwrite ทุก project — ก่อน import ของจริง กด <b>📸 Snapshot now</b>
      เพื่อให้ rollback ได้จากตารางด้านล่าง.
    </div>

    <!-- Daily snapshot table -->
    <div class="snapshots">
      <div class="snapshots-head">
        <span>📅 Daily snapshots</span>
        <span v-if="backups.length" class="snap-count">{{ backups.length }} kept</span>
        <button class="btn btn-sm" :disabled="loadingList" @click="loadBackupList" style="margin-left:auto">
          {{ loadingList ? '⏳' : '↻' }} Refresh
        </button>
      </div>
      <div v-if="loadingList && !backups.length" class="snap-empty">Loading…</div>
      <div v-else-if="!backups.length" class="snap-empty">
        <div class="empty-icon">📭</div>
        <div>ยังไม่มี snapshot</div>
        <div class="empty-hint">Hub สร้าง snapshot รายวันโดยอัตโนมัติ — กด <b>📸 Snapshot now</b> เพื่อสร้างทันที</div>
      </div>
      <table v-else class="snap-table">
        <thead>
          <tr>
            <th>Snapshot</th>
            <th style="width:140px">Modified</th>
            <th style="width:80px;text-align:right">Size</th>
            <th style="width:90px"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in backups" :key="b.name">
            <td><code>{{ b.name }}</code></td>
            <td class="ts">{{ b.modified }}</td>
            <td class="num">{{ b.size_kb }} KB</td>
            <td><button class="btn btn-sm" @click="restoreBackup(b)">↺ Restore</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.hint {
  font-size: 12.5px;
  color: var(--muted);
  margin: 0 0 var(--space-3);
  line-height: 1.6;
}
.hint code {
  background: var(--bg);
  padding: 1px 6px;
  border-radius: var(--radius-xs);
  font-size: 11.5px;
}
.actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: var(--space-3);
}
.warn-banner {
  background: var(--warn-soft);
  border: 1px solid rgba(255, 159, 10, 0.3);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  font-size: 12px;
  color: var(--text-secondary, var(--text));
  line-height: 1.5;
  margin-bottom: var(--space-4);
}

/* Daily snapshots block */
.snapshots {
  border-top: 1px solid var(--border-soft);
  padding-top: var(--space-3);
}
.snapshots-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: var(--space-3);
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: -0.01em;
}
.snap-count {
  font-size: 11px;
  color: var(--muted);
  font-weight: 400;
  background: var(--bg);
  padding: 2px 8px;
  border-radius: var(--radius-md);
}
.snap-empty {
  text-align: center;
  padding: 30px 16px;
  color: var(--muted);
  font-size: 12.5px;
}
.empty-icon { font-size: 32px; margin-bottom: 8px; opacity: 0.55; }
.empty-hint { font-size: 11.5px; margin-top: 6px; }

.snap-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.snap-table th, .snap-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border-soft);
  text-align: left;
}
.snap-table th {
  background: var(--bg);
  font-size: 11px;
  text-transform: uppercase;
  color: var(--muted);
  letter-spacing: 0.3px;
}
.snap-table code {
  font-family: "SF Mono", monospace;
  font-size: 11.5px;
  background: var(--bg);
  padding: 2px 7px;
  border-radius: var(--radius-xs);
}
.snap-table .ts  { color: var(--muted); font-family: "SF Mono", monospace; font-size: 11.5px; }
.snap-table .num { text-align: right; font-family: "SF Mono", monospace; font-size: 12px; color: var(--muted); }
</style>
