<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { apiCall } from '@/api/client'
import { useToast } from '@/composables/useToast'
import { useProjectStore } from '@/stores/projects'
import { useConfirm } from '@/composables/useConfirm'
import { useScaffoldDrift } from '@/composables/useScaffoldDrift'
import type { Project, SyncResult } from '@/api/types'
import ProjectEditModal from '@/components/ProjectEditModal.vue'
import ProjectAddModal from '@/components/ProjectAddModal.vue'

const router = useRouter()
const projects = useProjectStore()
const toast = useToast()
const { confirm } = useConfirm()
const drift = useScaffoldDrift()
const syncing = ref<string | null>(null)   // pid currently being synced

async function syncProject(p: Project) {
  if (p.exists === false) {
    toast.show('Cannot sync — project folder is missing', 'err')
    return
  }
  const ok = await confirm({
    title: `Sync "${p.name}" to canonical scaffold?`,
    desc:
      'Copies the latest preflight helpers, template validator, hook, and ' +
      'design-rule scripts from scaffold/' + p.type + ' into this project. ' +
      'Existing files that differ are backed up to *.bak_synct_<ts> before ' +
      'overwriting.',
    okLabel: 'Sync now',
  })
  if (!ok) return
  syncing.value = p.id
  try {
    const r = await apiCall<SyncResult>(`/api/scaffold/sync/${p.id}`, {
      body: { include_pipeline_scripts: true, include_template: false },
    })
    if (r.ok) {
      toast.show(`✓ Synced ${p.name}`, 'ok')
      await drift.refresh()
    } else {
      toast.show(`Sync failed (rc=${r.returncode}). See console.`, 'err')
      // eslint-disable-next-line no-console
      console.error('[sync stderr]', r.stderr)
      // eslint-disable-next-line no-console
      console.log('[sync stdout]', r.stdout)
    }
  } finally {
    syncing.value = null
  }
}

const editing = ref<Project | null>(null)
const showAddForm = ref(false)
const showAddModal = ref(false)

// Bulk-sync state — drift-bar at top of list lets the operator pick
// many drifted projects and sync them in one action instead of clicking
// "↻ Sync now" on each card.
const selectedPids = ref<Set<string>>(new Set())
const bulkSyncing = ref(false)

function isSelectable(p: Project): boolean {
  return p.exists !== false && drift.badgeFor(p.id).cls !== 'ok'
}
function toggleSelect(pid: string) {
  if (selectedPids.value.has(pid)) selectedPids.value.delete(pid)
  else selectedPids.value.add(pid)
  // Force reactivity (Set mutation isn't reactive in Vue out of box)
  selectedPids.value = new Set(selectedPids.value)
}
const driftedProjectIds = computed<string[]>(() =>
  projects.all.filter(isSelectable).map((p) => p.id)
)
const allDriftedSelected = computed(() =>
  driftedProjectIds.value.length > 0 &&
  driftedProjectIds.value.every((id) => selectedPids.value.has(id))
)
function toggleSelectAllDrifted() {
  if (allDriftedSelected.value) selectedPids.value = new Set()
  else selectedPids.value = new Set(driftedProjectIds.value)
}
async function bulkSyncSelected() {
  const ids = Array.from(selectedPids.value)
  if (!ids.length) return
  const ok = await confirm({
    title: `Sync ${ids.length} project${ids.length > 1 ? 's' : ''}?`,
    desc:
      `Each project will be synced sequentially. Files that differ get backed ` +
      `up to *.bak_synct_<ts> before overwrite. Pipeline scripts are included; ` +
      `templates are NOT (use single-card Sync now if you also want template overwrite).`,
    okLabel: 'Sync all',
  })
  if (!ok) return
  bulkSyncing.value = true
  let okCount = 0
  let failCount = 0
  for (const pid of ids) {
    try {
      const r = await apiCall<{ ok?: boolean }>(`/api/scaffold/sync/${pid}`, {
        body: { include_pipeline_scripts: true, include_template: false },
        silent: true,
      })
      if (r.ok) okCount++; else failCount++
    } catch {
      failCount++
    }
  }
  toast.show(
    failCount === 0 ? `✓ Synced ${okCount} project${okCount > 1 ? 's' : ''}`
                    : `Synced ${okCount} ok, ${failCount} failed (see console)`,
    failCount === 0 ? 'ok' : 'warn',
    failCount === 0 ? 4000 : 8000,
  )
  selectedPids.value = new Set()
  bulkSyncing.value = false
  await drift.refresh()
}

// ── Filters ────────────────────────────────────────────
const search = ref('')
const filterPhase = ref<'all' | 'active' | 'planning' | 'paused'>('all')
const filterType = ref<'all' | 'full-pipeline' | 'manual-testing' | 'playwright-only'>('all')
const filterCompany  = ref<string>('')   // '' = all, '__none__' = projects without company
const filterCategory = ref<string>('')

// ── Discover ───────────────────────────────────────────
interface DiscoverHit { path: string; type?: string; has_playwright?: boolean }
const discovered = ref<DiscoverHit[]>([])
const discovering = ref(false)
const showDiscover = ref(false)

const addForm = reactive({
  id:    '',
  name:  '',
  path:  '',
  type:  'full-pipeline' as Project['type'],
  color: '#0071E3',
})

const slugify = (s: string) =>
  s.toLowerCase().replace(/[^a-z0-9-_]+/g, '-').replace(/^-|-$/g, '')

// Auto-fill id when name is typed (only if user hasn't edited id manually)
const idTouched = ref(false)
function onNameInput() {
  if (!idTouched.value) addForm.id = slugify(addForm.name)
}

const phaseDot = (p?: string) => ({ active: '🟢', planning: '🟡', paused: '⚪' }[p || 'active'] || '🟢')

const NONE = '__none__'
const companies = computed<string[]>(() => {
  const set = new Set<string>()
  for (const p of projects.all) if (p.company) set.add(p.company)
  return Array.from(set).sort()
})
const categories = computed<string[]>(() => {
  const set = new Set<string>()
  for (const p of projects.all) if (p.category) set.add(p.category)
  return Array.from(set).sort()
})
const hasUntaggedCompany  = computed(() => projects.all.some((p) => !p.company))
const hasUntaggedCategory = computed(() => projects.all.some((p) => !p.category))

const sortedProjects = computed(() => {
  const phaseRank = { active: 0, planning: 1, paused: 2 } as Record<string, number>
  const q = search.value.trim().toLowerCase()
  return projects.all
    .filter((p) => {
      if (filterPhase.value !== 'all' && (p.phase || 'active') !== filterPhase.value) return false
      if (filterType.value !== 'all' && p.type !== filterType.value) return false
      if (filterCompany.value === NONE) {
        if (p.company) return false
      } else if (filterCompany.value && p.company !== filterCompany.value) {
        return false
      }
      if (filterCategory.value === NONE) {
        if (p.category) return false
      } else if (filterCategory.value && p.category !== filterCategory.value) {
        return false
      }
      if (q && !(p.name + ' ' + p.id + ' ' + p.path + ' ' + (p.company || '') + ' ' + (p.category || '')).toLowerCase().includes(q)) return false
      return true
    })
    .sort((a, b) => {
      // Missing folders to the top so they're impossible to miss
      if ((a.exists === false) !== (b.exists === false)) return a.exists === false ? -1 : 1
      const pa = phaseRank[a.phase || 'active'] ?? 0
      const pb = phaseRank[b.phase || 'active'] ?? 0
      if (pa !== pb) return pa - pb
      return a.name.localeCompare(b.name)
    })
})

const filterActive = computed(() =>
  search.value.trim() || filterPhase.value !== 'all' || filterType.value !== 'all'
  || filterCompany.value || filterCategory.value
)
function clearFilters() {
  search.value = ''
  filterPhase.value = 'all'
  filterType.value = 'all'
  filterCompany.value = ''
  filterCategory.value = ''
}

// Set of registered project IDs — used to grey-out Quick Add for folders
// whose slugified name would collide with an existing registration.
const registeredIds = computed(() => new Set(projects.all.map((p) => p.id)))

function discoveredId(d: DiscoverHit): string {
  const segments = d.path.split(/[\\/]/).filter(Boolean)
  return slugify(segments[segments.length - 1] || d.path)
}

async function discoverProjects() {
  discovering.value = true
  showDiscover.value = true
  try {
    const r = await apiCall<DiscoverHit[]>('/api/projects/discover', { silent: true })
    discovered.value = r || []
    if (!discovered.value.length) toast.show('ไม่พบ project ใหม่ใน C:\\Automation\\', 'info')
  } catch (e: unknown) {
    toast.show(`Discover failed: ${e instanceof Error ? e.message : 'unknown'}`, 'err')
    discovered.value = []
  } finally {
    discovering.value = false
  }
}

async function quickAddDiscovered(d: DiscoverHit) {
  const id = discoveredId(d)
  if (registeredIds.value.has(id)) {
    toast.show(`ID "${id}" registered อยู่แล้ว — ใช้ Edit แทน`, 'warn')
    return
  }
  const segments = d.path.split(/[\\/]/).filter(Boolean)
  const folderName = segments[segments.length - 1] || d.path
  try {
    await apiCall('/api/projects/add', {
      body: {
        id,
        name: folderName,
        path: d.path,
        type: d.type || 'full-pipeline',
        color: '#0071E3',
      },
    })
    toast.show(`Registered "${folderName}"`, 'ok')
    discovered.value = discovered.value.filter((x) => x.path !== d.path)
    await projects.load()
  } catch { /* apiCall toasted */ }
}

async function addProject() {
  if (!addForm.id || !addForm.name || !addForm.path) {
    toast.show('Fill id, name, path', 'warn')
    return
  }
  try {
    await apiCall('/api/projects/add', {
      body: {
        id:    addForm.id,
        name:  addForm.name,
        path:  addForm.path,
        type:  addForm.type,
        color: addForm.color,
      },
    })
    toast.show(`Project "${addForm.name}" registered`, 'ok')
    await projects.load()
    Object.assign(addForm, { id: '', name: '', path: '', type: 'full-pipeline', color: '#0071E3' })
    idTouched.value = false
    showAddForm.value = false
  } catch { /* apiCall toasted */ }
}

async function removeProject(p: Project) {
  const ok = await confirm({
    title: `Remove "${p.name}"?`,
    desc: `Folder จริง <b>ไม่ถูกลบ</b> — แค่เอาออกจาก Hub registration<br><br>เพิ่มกลับได้ภายหลังด้วย Auto Discover`,
    icon: '🗂️',
    okLabel: 'Remove',
    danger: true,
  })
  if (!ok) return
  try {
    await apiCall('/api/projects/remove', { body: { id: p.id } })
    toast.show('Project removed from registry', 'ok')
    await projects.load()
  } catch { /* apiCall toasted */ }
}

// Select + navigate to Dashboard so the user lands somewhere useful instead of
// silently swapping the global project state and leaving them on Projects.
function selectAndOpen(p: Project) {
  projects.select(p.id)
  router.push('/dashboard')
}

onMounted(() => {
  if (!projects.all.length) projects.load()
})
</script>

<template>
  <div class="card">
    <div class="card-title" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
      <span>🗂️ Projects</span>
      <span class="count">{{ sortedProjects.length }} of {{ projects.all.length }}</span>
      <div style="margin-left:auto;display:flex;gap:6px;flex-wrap:wrap">
        <button v-if="selectedPids.size > 0"
                class="btn btn-warn btn-sm"
                :disabled="bulkSyncing"
                @click="bulkSyncSelected">
          {{ bulkSyncing ? '⟳ Syncing…' : `↻ Sync ${selectedPids.size} selected` }}
        </button>
        <button v-if="driftedProjectIds.length > 0"
                class="btn btn-sm"
                :disabled="bulkSyncing"
                @click="toggleSelectAllDrifted">
          {{ allDriftedSelected ? '☐ Clear selection' : `☑ Select all drifted (${driftedProjectIds.length})` }}
        </button>
        <button class="btn btn-sm" @click="discoverProjects" :disabled="discovering">
          <span v-if="discovering">⏳ Scanning…</span>
          <span v-else>🔍 Auto Discover</span>
        </button>
        <button class="btn btn-primary btn-sm" @click="showAddModal = true">
          ➕ Add Project
        </button>
      </div>
    </div>

    <!-- Filter bar -->
    <div class="filter-bar">
      <div class="search-box">
        <span class="search-icon">🔍</span>
        <input v-model="search" type="text" placeholder="Search name, id, path, company, category…" />
      </div>
      <select v-model="filterPhase" class="filter-sel" title="Phase">
        <option value="all">All phases</option>
        <option value="active">🟢 Active</option>
        <option value="planning">🟡 Planning</option>
        <option value="paused">⚪ Paused</option>
      </select>
      <select v-model="filterType" class="filter-sel" title="Type">
        <option value="all">All types</option>
        <option value="full-pipeline">full-pipeline</option>
        <option value="manual-testing">manual-testing</option>
        <option value="playwright-only">playwright-only</option>
        <option value="pytest-only">pytest-only</option>
      </select>
      <select v-if="companies.length || hasUntaggedCompany" v-model="filterCompany" class="filter-sel" title="Company">
        <option value="">All companies</option>
        <option v-for="c in companies" :key="'co-'+c" :value="c">🏢 {{ c }}</option>
        <option v-if="hasUntaggedCompany" :value="NONE">◌ Other (no company)</option>
      </select>
      <select v-if="categories.length || hasUntaggedCategory" v-model="filterCategory" class="filter-sel" title="Category">
        <option value="">All categories</option>
        <option v-for="c in categories" :key="'ca-'+c" :value="c">📁 {{ c }}</option>
        <option v-if="hasUntaggedCategory" :value="NONE">◌ Other (no category)</option>
      </select>
      <button v-if="filterActive" class="btn btn-sm" @click="clearFilters">× Clear filters</button>
    </div>

    <!-- Add form (collapses) -->
    <div v-if="showAddForm" class="add-form">
      <p class="hint">
        Register a folder ที่มีอยู่แล้ว เป็น Hub project — สำหรับ scaffold/git clone ให้ใช้
        <a href="/" class="legacy-link">legacy /projects</a>
      </p>
      <div class="form-grid">
        <div class="field">
          <label>Display Name</label>
          <input v-model="addForm.name" @input="onNameInput" placeholder="My Project" />
        </div>
        <div class="field">
          <label>ID (auto-slugified)</label>
          <input v-model="addForm.id" @input="idTouched = true" placeholder="my-project" />
        </div>
        <div class="field" style="grid-column: span 2">
          <label>Path (relative to C:\Automation\)</label>
          <input v-model="addForm.path" placeholder="MyOrg/my-project" />
        </div>
        <div class="field">
          <label>Type</label>
          <select v-model="addForm.type">
            <option value="full-pipeline">full-pipeline</option>
            <option value="manual-testing">manual-testing</option>
            <option value="playwright-only">playwright-only</option>
            <option value="pytest-only">pytest-only</option>
          </select>
        </div>
        <div class="field">
          <label>Color</label>
          <div style="display:flex;gap:6px">
            <input v-model="addForm.color" type="color" style="width:50px;padding:2px" />
            <input v-model="addForm.color" type="text" />
          </div>
        </div>
      </div>
      <button class="btn btn-primary" @click="addProject" style="margin-top:10px">➕ Register</button>
    </div>
  </div>

  <!-- Discover results -->
  <div v-if="showDiscover" class="card discover-card">
    <div class="card-title" style="display:flex;align-items:center">
      <span>🔍 Auto Discover Results</span>
      <span class="count" style="margin-left:8px">{{ discovered.length }} folder(s) ที่ยังไม่ register</span>
      <button class="btn btn-sm" @click="showDiscover = false" style="margin-left:auto">× Close</button>
    </div>
    <div v-if="discovering" class="empty">Scanning C:\Automation\…</div>
    <div v-else-if="!discovered.length" class="empty">
      <div class="empty-icon">🎯</div>
      <div>ทุก folder ที่มี <code>playwright.config.ts</code> register ใน Hub แล้ว</div>
    </div>
    <div v-else class="discover-list">
      <div v-for="d in discovered" :key="d.path" class="discover-row"
           :class="{ 'discover-dup': registeredIds.has(discoveredId(d)) }">
        <div class="discover-info">
          <code class="discover-path">{{ d.path }}</code>
          <span class="discover-meta">
            <span v-if="d.type" class="type-pill">{{ d.type }}</span>
            <span v-if="d.has_playwright" class="meta-flag">🎭 has Playwright</span>
            <span v-if="registeredIds.has(discoveredId(d))" class="dup-badge">⚠ id "{{ discoveredId(d) }}" already registered</span>
          </span>
        </div>
        <button class="btn btn-sm btn-primary" @click="quickAddDiscovered(d)"
                :disabled="registeredIds.has(discoveredId(d))">+ Quick Add</button>
      </div>
    </div>
  </div>

  <!-- Skeleton on first load -->
  <div v-if="projects.loading && !projects.all.length" class="grid">
    <div v-for="i in 4" :key="i" class="proj-card skel">
      <div class="skel-bar w-60"></div>
      <div class="skel-bar w-30"></div>
      <div class="skel-bar w-80"></div>
    </div>
  </div>

  <!-- True empty: no projects registered at all -->
  <div v-else-if="!projects.all.length" class="card empty">
    <div class="empty-icon">📭</div>
    <div><b>ยังไม่มี project</b></div>
    <div class="empty-hint">Register folder ข้างบน หรือกด <b>🔍 Auto Discover</b></div>
  </div>

  <!-- Filter-excluded empty (different from "no projects") -->
  <div v-else-if="!sortedProjects.length" class="card empty">
    <div class="empty-icon">🔍</div>
    <div>ไม่พบ project ที่ตรงกับ filter ปัจจุบัน</div>
    <button class="btn btn-sm" @click="clearFilters" style="margin-top:10px">Clear filters</button>
  </div>

  <div v-else class="grid">
    <div v-for="p in sortedProjects" :key="p.id"
         class="proj-card"
         :class="{ 'is-current': p.id === projects.current, 'is-missing': p.exists === false }"
         :style="{ borderLeftColor: p.color || 'var(--primary)' }">
      <div class="proj-header">
        <input v-if="isSelectable(p)"
               type="checkbox"
               class="bulk-check"
               :checked="selectedPids.has(p.id)"
               @change="toggleSelect(p.id)"
               :title="`Add to bulk-sync selection (${drift.badgeFor(p.id).label})`" />
        <div class="proj-title">
          {{ phaseDot(p.phase) }} {{ p.name }}
          <span v-if="p.exists === false" class="missing-flag" title="Folder ไม่มีอยู่ในเครื่องนี้">⚠</span>
        </div>
        <span class="type-pill">{{ p.type }}</span>
      </div>

      <div class="proj-meta">
        <div><b>ID:</b> <code>{{ p.id }}</code></div>
        <div><b>Path:</b> <code>{{ p.path }}</code></div>
        <div v-if="p.company || p.category" class="taxonomy">
          <span v-if="p.company" class="tag-pill">🏢 {{ p.company }}</span>
          <span v-if="p.category" class="tag-pill">📁 {{ p.category }}</span>
        </div>
        <div v-if="p.figma_url" style="margin-top:4px">
          <a :href="p.figma_url" target="_blank" class="link-inline">🎨 Figma →</a>
        </div>
      </div>

      <!-- Enriched data row: status badges + last run -->
      <div v-if="p.exists !== false" class="proj-status">
        <span v-if="p.has_xlsx" class="status-pill ok" title="TCM Excel found in input/">📋 TCM</span>
        <span v-else class="status-pill mute" title="No TCM Excel yet">○ TCM</span>
        <span v-if="p.has_docx" class="status-pill ok" title="Report found in output/">📄 Report</span>
        <span v-else class="status-pill mute" title="No report yet">○ Report</span>
        <span v-if="(p.screenshot_count ?? 0) > 0" class="status-pill info" title="Screenshots in folder">
          📷 {{ p.screenshot_count }}
        </span>
        <span v-if="p.last_run" class="status-pill last-run" :title="`Last activity: ${p.last_run}`">
          ⏱ {{ p.last_run }}
        </span>
        <span v-else class="status-pill mute small">no runs yet</span>
        <span v-if="drift.badgeFor(p.id).show"
              class="status-pill"
              :class="`drift-${drift.badgeFor(p.id).cls}`"
              :title="drift.badgeFor(p.id).title">
          {{ drift.badgeFor(p.id).label }}
        </span>
      </div>
      <div v-else class="proj-status missing-banner">
        Folder <code>{{ p.path }}</code> หายไป — Pipeline จะ error
      </div>

      <div class="proj-actions">
        <button v-if="p.id !== projects.current" class="btn btn-sm btn-primary"
                :disabled="p.exists === false"
                @click="selectAndOpen(p)">
          Select &amp; Open →
        </button>
        <span v-else class="active-pill">CURRENT</span>
        <button class="btn btn-sm" @click="editing = p">Edit</button>
        <button v-if="drift.badgeFor(p.id).show && drift.badgeFor(p.id).cls !== 'ok'"
                class="btn btn-sm btn-warn"
                :disabled="syncing === p.id || p.exists === false"
                :title="drift.badgeFor(p.id).title"
                @click="syncProject(p)">
          {{ syncing === p.id ? '⟳ syncing…' : '↻ Sync now' }}
        </button>
        <button class="btn btn-sm btn-danger" @click="removeProject(p)" style="margin-left:auto">Remove</button>
      </div>
    </div>
  </div>

  <ProjectEditModal :project="editing" @close="editing = null" @saved="projects.load" />
  <ProjectAddModal :open="showAddModal" @close="showAddModal = false" @added="projects.load" />
</template>

<style scoped>
.count { font-size: 12px; color: var(--muted); font-weight: 400; }

.filter-bar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin: 12px 0 4px;
  flex-wrap: wrap;
}
.search-box {
  position: relative;
  flex: 1;
  min-width: 240px;
  max-width: 480px;
}
.search-icon {
  position: absolute;
  left: 10px; top: 50%;
  transform: translateY(-50%);
  font-size: 13px;
  color: var(--muted);
}
.search-box input {
  width: 100%;
  padding-left: 32px;
}
.filter-sel { font-size: 12.5px; min-width: 140px; }
.legacy-link { color: var(--primary); }

.discover-card { border-left: 3px solid var(--primary); }
.discover-list { display: flex; flex-direction: column; gap: 6px; }
.discover-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: var(--bg);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-soft);
}
.discover-row.discover-dup {
  opacity: 0.65;
  background: var(--warn-soft);
  border-color: rgba(255, 159, 10, 0.3);
}
.discover-info { flex: 1; min-width: 0; }
.discover-path {
  font-family: "SF Mono", "Cascadia Mono", monospace;
  font-size: 12px;
  color: var(--text);
  background: var(--card);
  padding: 2px 8px;
  border-radius: var(--radius-xs);
  display: inline-block;
}
.discover-meta { margin-left: 6px; font-size: 11.5px; color: var(--muted); }
.meta-flag { margin-left: 6px; }
.dup-badge {
  margin-left: 6px;
  color: var(--warn);
  font-weight: 600;
}
[data-theme="dark"] .dup-badge { color: var(--warn); }

.add-form {
  background: var(--bg);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  padding: var(--space-4) var(--space-5);
  margin-top: var(--space-3);
}
.hint { font-size: 12px; color: var(--muted); margin-bottom: 10px; }
.form-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px 14px; max-width: 720px; }
.field label { display: block; font-size: 11px; color: var(--muted); margin-bottom: 4px; font-weight: 600; }
.field input, .field select { width: 100%; }

.empty {
  text-align: center;
  padding: 50px 24px;
  color: var(--muted);
}
.empty-icon { font-size: 36px; margin-bottom: 10px; opacity: .55; }
.empty b { color: var(--text); font-weight: 600; }
.empty-hint { font-size: 12.5px; margin-top: 6px; }

/* Card grid — caps each card width so they don't sprawl on wide screens */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 380px));
  gap: var(--space-3);
  justify-content: start;
}
@media (max-width: 700px) {
  .grid { grid-template-columns: 1fr; }
}
@media (max-width: 640px) {
  /* Add/Edit project modal form: 2-col → 1-col */
  .form-grid { grid-template-columns: 1fr; }
  /* Filter bar: search + selects each get their own row when too narrow */
  .search-box { flex: 1 1 100%; min-width: 0; }
  .filter-sel { flex: 1 1 calc(50% - 8px); max-width: 100%; }
  /* Toolbar buttons in card-title (Sync / Select all drifted / Auto Discover /
     Add Project) — bump tap target on mobile */
  .card-title .btn-sm { min-height: 40px; }
}
.proj-card {
  background: var(--card);
  border: 1px solid var(--border-soft);
  border-left: 4px solid var(--primary);
  border-radius: var(--radius-md);
  padding: var(--space-4) var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  box-shadow: var(--shadow-sm);
  transition: transform var(--duration-fast) var(--ease),
              box-shadow var(--duration-fast) var(--ease);
}
.proj-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
.proj-card.is-current {
  border-left-color: var(--success);
  box-shadow: 0 0 0 2px rgba(52, 199, 89, .18), var(--shadow-sm);
}
.proj-card.is-missing {
  border-left-color: var(--danger);
  background: var(--danger-soft);
}
.missing-flag {
  display: inline-block;
  margin-left: 4px;
  color: var(--danger);
  cursor: help;
}
.missing-banner {
  font-size: 11.5px;
  color: var(--danger);
  background: var(--card);
  border: 1px dashed var(--danger);
  border-radius: var(--radius-xs);
  padding: 5px 10px;
  margin-top: 4px;
}
.missing-banner code {
  background: var(--bg);
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 11px;
}

.proj-header { display: flex; align-items: center; gap: var(--space-2); }
.bulk-check { width: 16px; height: 16px; flex-shrink: 0; cursor: pointer; }
.proj-title {
  font-weight: 600; font-size: 14px;
  color: var(--text);
  letter-spacing: -0.01em;
  flex: 1;
}
.type-pill {
  font-size: 10.5px;
  background: var(--primary-soft);
  color: var(--primary-dk, var(--primary));
  padding: 2px 8px;
  border-radius: var(--radius-md);
  font-weight: 600;
}
.proj-meta { font-size: 12px; color: var(--muted); line-height: 1.55; }
.proj-meta code {
  font-family: "SF Mono", "Cascadia Mono", monospace;
  font-size: 11.5px;
  background: var(--code-bg, var(--bg));
  padding: 1px 6px;
  border-radius: var(--radius-xs);
  color: var(--text);
}
.taxonomy { margin-top: 4px; display: flex; gap: 4px; flex-wrap: wrap; }
.tag-pill {
  font-size: 10.5px;
  background: var(--bg);
  border: 1px solid var(--border-soft);
  color: var(--text-secondary, var(--text));
  padding: 1px 7px;
  border-radius: var(--radius-md);
}
.link-inline { color: var(--primary); font-size: 12px; }

/* Enriched-data status pills */
.proj-status {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 2px;
}
.status-pill {
  font-size: 10.5px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-soft);
  white-space: nowrap;
}
.status-pill.ok       { background: var(--success-soft); color: var(--success); border-color: rgba(48, 209, 88, 0.3); }
.status-pill.mute     { background: var(--bg);           color: var(--muted); }
.status-pill.info     { background: var(--primary-soft); color: var(--primary-dk, var(--primary)); border-color: rgba(0, 113, 227, 0.3); }
.status-pill.last-run { background: var(--bg);           color: var(--text-secondary, var(--text)); font-family: "SF Mono", monospace; font-weight: 500; }
.status-pill.small    { font-size: 10px; opacity: 0.8; }
.status-pill.drift-ok   { background: var(--success-soft); color: var(--success); border-color: rgba(48, 209, 88, 0.3); }
.status-pill.drift-warn { background: var(--warn-soft);    color: var(--warn);    border-color: rgba(255, 159, 10, 0.3); }
.status-pill.drift-err  { background: var(--danger-soft);  color: var(--danger);  border-color: rgba(255, 69, 58, 0.3); }
[data-theme="dark"] .status-pill.ok { color: var(--success); }
.btn.btn-warn { background: var(--warn-soft); color: var(--warn); border: 1px solid rgba(255, 159, 10, 0.4); }
.btn.btn-warn:hover { background: rgba(255, 159, 10, 0.28); }

.proj-actions { display: flex; gap: var(--space-2); align-items: center; margin-top: 6px; }
.active-pill {
  font-size: 10.5px;
  background: var(--success-soft);
  color: var(--success);
  padding: 3px 9px;
  border-radius: var(--radius-md);
  font-weight: 700;
}
[data-theme="dark"] .active-pill { color: var(--success); }
.btn-sm { padding: 5px 11px; font-size: 12px; }

/* Skeleton loader */
.skel { gap: 10px; }
.skel-bar {
  height: 12px;
  background: linear-gradient(90deg, var(--bg) 25%, var(--border-soft) 50%, var(--bg) 75%);
  background-size: 200% 100%;
  border-radius: var(--radius-xs);
  animation: shimmer 1.4s linear infinite;
}
.skel-bar.w-60 { width: 60%; }
.skel-bar.w-30 { width: 30%; }
.skel-bar.w-80 { width: 80%; }
@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
