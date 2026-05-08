<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { apiCall } from '@/api/client'
import { useProjectStore } from '@/stores/projects'
import { useToast } from '@/composables/useToast'
import { copyTextWithFallback } from '@/utils/clipboard'

interface Shot {
  filepath: string       // canonical relative path used by /api/screenshots/<path>
  name: string
  tcid?: string
  size_kb?: number
  modified?: string      // formatted like "27 Apr 2026 14:30"
}

type ViewMode = 'grid' | 'compact' | 'list'
type GroupBy = 'none' | 'date'

const projects = useProjectStore()
const toast = useToast()
const shots = ref<Shot[]>([])
const loading = ref(true)
const lightbox = ref<string | null>(null)

const viewMode = ref<ViewMode>((localStorage.getItem('fp_shots_view') as ViewMode) || 'grid')
const groupBy  = ref<GroupBy>((localStorage.getItem('fp_shots_group') as GroupBy) || 'none')
const search   = ref('')

watch(viewMode, (v) => localStorage.setItem('fp_shots_view', v))
watch(groupBy,  (v) => localStorage.setItem('fp_shots_group', v))

async function copyPath() {
  if (!projects.current) return
  let path = ''
  try {
    const r = await apiCall<{ path: string }>(
      `/api/path/screenshots?p=${projects.current}`,
      { silent: true }
    )
    path = r.path || ''
  } catch {
    toast.show(`Couldn't resolve screenshots/ path`, 'err')
    return
  }
  if (!path) {
    toast.show('No path returned for screenshots/', 'err')
    return
  }
  const ok = await copyTextWithFallback(path)
  if (ok) {
    toast.show(`📋 คัดลอก path แล้ว — วางใน Win+R หรือ Explorer address bar:\n${path}`, 'ok')
  } else {
    toast.show(`Clipboard ใช้ไม่ได้ — คัดลอก path นี้เอง:\n${path}`, 'warn', 12000)
  }
}

async function load() {
  if (!projects.current) return
  loading.value = true
  try {
    const r = await apiCall<{ files?: Shot[] } | Shot[]>(`/api/screenshots/list?p=${projects.current}`, { silent: true })
    shots.value = Array.isArray(r) ? r : (r as { files: Shot[] }).files || []
  } catch {
    shots.value = []
  } finally {
    loading.value = false
  }
}

// FIX: route is /api/screenshots/<path:filepath>?p=... (path param), not /api/screenshots/file?p=&f=
const shotUrl = (s: Shot) =>
  `/api/screenshots/${encodeURI(s.filepath || s.name)}?p=${encodeURIComponent(projects.current)}`

onMounted(async () => {
  if (!projects.all.length) await projects.load()
  load()
})
watch(() => projects.current, load)

const downloadAllUrl = computed(() => `/api/screenshots/download?p=${projects.current}`)

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return shots.value
  return shots.value.filter((s) =>
    (s.name + ' ' + (s.tcid || '')).toLowerCase().includes(q)
  )
})

interface ShotGroup { label: string; items: Shot[] }
const grouped = computed<ShotGroup[]>(() => {
  if (groupBy.value !== 'date') return [{ label: '', items: filtered.value }]
  // Group by relative date bucket
  const today = new Date(); today.setHours(0, 0, 0, 0)
  const yest  = new Date(today); yest.setDate(yest.getDate() - 1)
  const week  = new Date(today); week.setDate(week.getDate() - 7)
  const buckets: Record<string, Shot[]> = {
    'วันนี้': [], 'เมื่อวาน': [], '7 วันที่ผ่านมา': [], 'เก่ากว่า': [],
  }
  for (const s of filtered.value) {
    const d = parseDate(s.modified)
    let key = 'เก่ากว่า'
    if (d) {
      if (d >= today) key = 'วันนี้'
      else if (d >= yest) key = 'เมื่อวาน'
      else if (d >= week) key = '7 วันที่ผ่านมา'
    }
    buckets[key].push(s)
  }
  return Object.entries(buckets)
    .filter(([, items]) => items.length)
    .map(([label, items]) => ({ label, items }))
})

function parseDate(s?: string): Date | null {
  if (!s) return null
  // Format: "27 Apr 2026 14:30"
  const t = Date.parse(s)
  return isNaN(t) ? null : new Date(t)
}
</script>

<template>
  <div class="card">
    <div class="card-title" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
      <span>📷 Screenshots</span>
      <span class="count">{{ filtered.length }}/{{ shots.length }} image{{ shots.length === 1 ? '' : 's' }}</span>
      <div style="margin-left:auto;display:flex;gap:6px;flex-wrap:wrap">
        <button class="btn btn-sm" @click="copyPath" title="คัดลอก absolute path ไป clipboard — วางใน Win+R หรือ Explorer address bar">📋 Copy path</button>
        <button class="btn btn-sm" @click="load">↻ Refresh</button>
        <a v-if="shots.length" :href="downloadAllUrl" class="btn btn-sm btn-primary" target="_blank">⬇ Download all (zip)</a>
      </div>
    </div>

    <!-- Toolbar: search + view toggle + group toggle -->
    <div v-if="shots.length" class="toolbar">
      <input v-model="search" type="text" placeholder="ค้นหา TC ID หรือชื่อไฟล์…" class="search" />

      <div class="seg" role="group" aria-label="View mode">
        <button class="seg-btn" :class="{ active: viewMode === 'grid' }" @click="viewMode = 'grid'" title="Grid (large)">
          <span aria-hidden="true">▦</span> Grid
        </button>
        <button class="seg-btn" :class="{ active: viewMode === 'compact' }" @click="viewMode = 'compact'" title="Compact (small)">
          <span aria-hidden="true">▪▪</span> Compact
        </button>
        <button class="seg-btn" :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'" title="Detail list">
          <span aria-hidden="true">≡</span> List
        </button>
      </div>

      <label class="group-toggle">
        <input type="checkbox" :checked="groupBy === 'date'" @change="groupBy = groupBy === 'date' ? 'none' : 'date'" />
        Group by date
      </label>
    </div>

    <div v-if="loading" class="empty">Loading…</div>
    <div v-else-if="!shots.length" class="empty">
      <div class="empty-icon">📭</div>
      <div><b>ยังไม่มี screenshots</b></div>
      <div class="empty-hint">รัน <b>Stage 5 (Run Tests)</b> ใน Pipeline เพื่อสร้าง screenshots อัตโนมัติ</div>
    </div>
    <div v-else-if="!filtered.length" class="empty">
      <div class="empty-icon">🔍</div>
      <div>ไม่พบรูปที่ตรงกับ "<b>{{ search }}</b>"</div>
      <button class="btn btn-sm" @click="search = ''" style="margin-top:10px">Clear search</button>
    </div>

    <template v-else>
      <div v-for="g in grouped" :key="g.label || 'all'" class="group">
        <div v-if="g.label" class="group-head">{{ g.label }} <span class="group-count">{{ g.items.length }}</span></div>

        <!-- Grid view -->
        <div v-if="viewMode === 'grid'" class="grid grid-large">
          <div v-for="s in g.items" :key="s.filepath" class="shot-card" @click="lightbox = shotUrl(s)">
            <div class="thumb-wrap"><img :src="shotUrl(s)" :alt="s.name" loading="lazy" /></div>
            <div class="caption" :title="s.name">
              <span class="cap-title">{{ s.tcid || s.name }}</span>
              <span v-if="s.size_kb" class="cap-meta">{{ s.size_kb }} KB</span>
            </div>
          </div>
        </div>

        <!-- Compact view -->
        <div v-else-if="viewMode === 'compact'" class="grid grid-compact">
          <div v-for="s in g.items" :key="s.filepath" class="shot-card compact" @click="lightbox = shotUrl(s)" :title="s.name">
            <div class="thumb-wrap"><img :src="shotUrl(s)" :alt="s.name" loading="lazy" /></div>
            <div class="caption compact-cap">{{ s.tcid || s.name }}</div>
          </div>
        </div>

        <!-- List view -->
        <ul v-else class="list">
          <li v-for="s in g.items" :key="s.filepath" class="list-row" @click="lightbox = shotUrl(s)">
            <img :src="shotUrl(s)" :alt="s.name" class="list-thumb" loading="lazy" />
            <div class="list-info">
              <div class="list-title">{{ s.tcid || s.name }}</div>
              <div class="list-meta">
                <span>{{ s.name }}</span>
                <span v-if="s.size_kb">· {{ s.size_kb }} KB</span>
                <span v-if="s.modified">· {{ s.modified }}</span>
              </div>
            </div>
            <a class="btn btn-sm" :href="shotUrl(s)" target="_blank" @click.stop title="Open original">↗</a>
          </li>
        </ul>
      </div>
    </template>
  </div>

  <!-- Lightbox -->
  <Teleport to="body">
    <div v-if="lightbox" class="lightbox" @click="lightbox = null">
      <img :src="lightbox" alt="" />
      <button class="lightbox-close" aria-label="Close" @click="lightbox = null">×</button>
    </div>
  </Teleport>
</template>

<style scoped>
.count { font-size: 12px; color: var(--muted); font-weight: 400; }

/* Toolbar */
.toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: var(--space-3);
}
.search {
  flex: 1;
  min-width: 200px;
  max-width: 360px;
  font-size: 12.5px;
}
.seg {
  display: inline-flex;
  background: var(--bg);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  padding: 3px;
}
.seg-btn {
  background: transparent;
  border: none;
  font-family: inherit;
  font-size: 12px;
  color: var(--muted);
  padding: 5px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  transition: all var(--duration-fast) var(--ease);
}
.seg-btn:hover { color: var(--text); }
.seg-btn.active {
  background: var(--card);
  color: var(--text);
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}
.group-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--muted);
  cursor: pointer;
  user-select: none;
}
.group-toggle input { width: 14px; margin: 0; }

/* Group sections */
.group + .group { margin-top: var(--space-4); }
.group-head {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-secondary, var(--muted));
  text-transform: uppercase;
  letter-spacing: .5px;
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border-soft);
  display: flex;
  align-items: center;
  gap: 8px;
}
.group-count {
  font-size: 11px;
  background: var(--bg);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  padding: 1px 8px;
  color: var(--muted);
  font-weight: 500;
  text-transform: none;
  letter-spacing: 0;
}

/* Empty states */
.empty {
  text-align: center;
  padding: 60px 24px;
  color: var(--muted);
  font-style: normal;
}
.empty-icon { font-size: 42px; margin-bottom: 12px; opacity: .55; }
.empty b { color: var(--text); font-weight: 600; }
.empty-hint { font-size: 12.5px; margin-top: 6px; }

/* Grid views */
.grid { display: grid; gap: var(--space-3); }
.grid-large { grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); }
.grid-compact { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 10px; }
@media (min-width: 1400px) {
  .grid-large { grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }
}

.shot-card {
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  overflow: hidden;
  cursor: pointer;
  background: var(--card);
  box-shadow: var(--shadow-sm);
  transition: transform var(--duration-fast) var(--ease),
              box-shadow var(--duration-fast) var(--ease),
              border-color var(--duration-fast) var(--ease);
}
.shot-card:hover {
  border-color: var(--primary);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
.thumb-wrap {
  width: 100%;
  aspect-ratio: 16 / 10;
  overflow: hidden;
  background: var(--bg);
}
.shot-card img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform var(--duration) var(--ease);
}
.shot-card:hover img { transform: scale(1.04); }
.caption {
  padding: 8px 12px;
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--card);
  border-top: 1px solid var(--border-soft);
  display: flex;
  justify-content: space-between;
  gap: 8px;
}
.cap-title {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}
.cap-meta {
  font-size: 10.5px;
  color: var(--muted);
  flex-shrink: 0;
}

/* Compact-specific */
.shot-card.compact .thumb-wrap { aspect-ratio: 1 / 1; }
.compact-cap {
  padding: 5px 8px;
  font-size: 10.5px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
}

/* List view */
.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.list-row {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 8px 12px;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  background: var(--card);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease);
}
.list-row:hover {
  border-color: var(--primary);
  background: var(--primary-soft);
  transform: translateX(2px);
}
.list-thumb {
  width: 64px;
  height: 40px;
  object-fit: cover;
  border-radius: var(--radius-xs);
  flex-shrink: 0;
  background: var(--bg);
}
.list-info { flex: 1; min-width: 0; }
.list-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.list-meta {
  font-size: 11.5px;
  color: var(--muted);
  margin-top: 2px;
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.list-meta span:first-child {
  font-family: "SF Mono", monospace;
  font-size: 11px;
}

/* Lightbox */
.lightbox {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.92);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  cursor: zoom-out;
  padding: 40px;
}
.lightbox img {
  max-width: 95vw;
  max-height: 95vh;
  border-radius: var(--radius-md);
  box-shadow: 0 0 60px rgba(0, 0, 0, 0.5);
}
.lightbox-close {
  position: absolute;
  top: 20px; right: 24px;
  width: 40px; height: 40px;
  background: rgba(255, 255, 255, 0.15);
  color: white;
  border: none;
  border-radius: 50%;
  font-size: 24px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--duration-fast) var(--ease);
}
.lightbox-close:hover { background: rgba(255, 255, 255, 0.25); }
.btn-sm { padding: 5px 11px; font-size: 12px; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; }
</style>
