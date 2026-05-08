<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useProjectStore } from '@/stores/projects'

const store = useProjectStore()

// ── UI state ───────────────────────────────────────────────────────────
const open = ref(false)
const search = ref('')
const filterCompany  = ref<string>(localStorage.getItem('fp_switcher_company')  || '')
const filterCategory = ref<string>(localStorage.getItem('fp_switcher_category') || '')

watch(filterCompany,  (v) => localStorage.setItem('fp_switcher_company', v))
watch(filterCategory, (v) => localStorage.setItem('fp_switcher_category', v))

const rootEl = ref<HTMLElement | null>(null)
const searchInput = ref<HTMLInputElement | null>(null)

// ── Derived data ───────────────────────────────────────────────────────
const phaseDot = (phase?: string) => ({
  active: '🟢', planning: '🟡', paused: '⚪',
}[phase || 'active'] || '🟢')

// Unique non-empty companies / categories present in the project list
const companies = computed<string[]>(() => {
  const set = new Set<string>()
  for (const p of store.all) if (p.company) set.add(p.company)
  return Array.from(set).sort()
})
const categories = computed<string[]>(() => {
  const set = new Set<string>()
  for (const p of store.all) if (p.category) set.add(p.category)
  return Array.from(set).sort()
})

// Sentinel: filter value === '__none__' means "project has no company/category set"
const NONE = '__none__'

const filteredProjects = computed(() => {
  const q = search.value.trim().toLowerCase()
  return store.all.filter((p) => {
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
    if (q && !(p.name + ' ' + p.id + ' ' + (p.company || '') + ' ' + (p.category || ''))
              .toLowerCase().includes(q)) return false
    return true
  })
})

// True if at least one project has no company / category — show "Other" chip only when useful
const hasUntaggedCompany  = computed(() => store.all.some((p) => !p.company))
const hasUntaggedCategory = computed(() => store.all.some((p) => !p.category))

const filterActive = computed(() =>
  !!filterCompany.value || !!filterCategory.value || !!search.value.trim()
)

const currentMeta = computed(() => store.all.find((p) => p.id === store.current))

// ── Behavior ───────────────────────────────────────────────────────────
function toggle() {
  open.value = !open.value
  if (open.value) {
    nextTick(() => searchInput.value?.focus())
  }
}

function pick(id: string) {
  store.select(id)
  open.value = false
  search.value = ''
}

function clearFilters() {
  filterCompany.value = ''
  filterCategory.value = ''
  search.value = ''
}

function onClickOutside(e: MouseEvent) {
  if (!rootEl.value) return
  if (!rootEl.value.contains(e.target as Node)) open.value = false
}

function onKey(e: KeyboardEvent) {
  if (!open.value) return
  if (e.key === 'Escape') { open.value = false; return }
  if (e.key === 'Enter' && filteredProjects.value.length === 1) {
    pick(filteredProjects.value[0].id)
  }
}

onMounted(() => {
  if (!store.all.length) store.load()
  document.addEventListener('click', onClickOutside)
  document.addEventListener('keydown', onKey)
})
onUnmounted(() => {
  document.removeEventListener('click', onClickOutside)
  document.removeEventListener('keydown', onKey)
})
</script>

<template>
  <div ref="rootEl" class="switcher">
    <label>Project:</label>

    <!-- Trigger button — replaces native <select> -->
    <button v-if="store.all.length" class="trigger" :class="{ open, 'has-filter': filterActive }"
            @click.stop="toggle"
            :title="filterActive ? `Filter active: ${filterCompany || ''}${filterCompany && filterCategory ? ' · ' : ''}${filterCategory || ''}` : ''">
      <span class="trig-text">
        <template v-if="currentMeta">
          {{ phaseDot(currentMeta.phase) }} {{ currentMeta.name }}
        </template>
        <template v-else>Select project…</template>
      </span>
      <span v-if="filterActive" class="filter-dot" aria-label="filter active">●</span>
      <span class="trig-caret">▾</span>
    </button>
    <span v-else class="loading">loading…</span>

    <!-- Dropdown panel -->
    <div v-if="open" class="panel" @click.stop>
      <input ref="searchInput" v-model="search" type="text"
             class="search" placeholder="Search project, company, category…" />

      <!-- Company / Category filter chips -->
      <div v-if="companies.length || categories.length || hasUntaggedCompany || hasUntaggedCategory" class="filter-row">
        <div v-if="companies.length || hasUntaggedCompany" class="filter-group">
          <span class="filter-label">Company</span>
          <div class="chips">
            <button class="chip" :class="{ active: filterCompany === '' }" @click="filterCompany = ''">All</button>
            <button v-for="c in companies" :key="'co-'+c"
                    class="chip" :class="{ active: filterCompany === c }"
                    @click="filterCompany = filterCompany === c ? '' : c">
              🏢 {{ c }}
            </button>
            <button v-if="hasUntaggedCompany"
                    class="chip chip-other" :class="{ active: filterCompany === NONE }"
                    @click="filterCompany = filterCompany === NONE ? '' : NONE"
                    title="Projects with no Company set">
              ◌ Other
            </button>
          </div>
        </div>
        <div v-if="categories.length || hasUntaggedCategory" class="filter-group">
          <span class="filter-label">Category</span>
          <div class="chips">
            <button class="chip" :class="{ active: filterCategory === '' }" @click="filterCategory = ''">All</button>
            <button v-for="c in categories" :key="'ca-'+c"
                    class="chip" :class="{ active: filterCategory === c }"
                    @click="filterCategory = filterCategory === c ? '' : c">
              📁 {{ c }}
            </button>
            <button v-if="hasUntaggedCategory"
                    class="chip chip-other" :class="{ active: filterCategory === NONE }"
                    @click="filterCategory = filterCategory === NONE ? '' : NONE"
                    title="Projects with no Category set">
              ◌ Other
            </button>
          </div>
        </div>
      </div>

      <!-- No taxonomy hint — only when NO project has either field set -->
      <div v-else class="no-tax">
        <span>No <code>company</code> / <code>category</code> tags yet —</span>
        <router-link to="/projects" @click="open = false">set in Projects → Edit</router-link>
      </div>

      <!-- Project list -->
      <div class="proj-list">
        <button v-for="p in filteredProjects" :key="p.id"
                class="proj-row" :class="{ current: p.id === store.current }"
                @click="pick(p.id)">
          <span class="proj-dot">{{ phaseDot(p.phase) }}</span>
          <span class="proj-name">{{ p.name }}</span>
          <span v-if="p.company" class="proj-tag">🏢 {{ p.company }}</span>
          <span v-if="p.category" class="proj-tag">📁 {{ p.category }}</span>
          <span v-if="p.id === store.current" class="proj-mark" aria-hidden="true">✓</span>
        </button>
        <div v-if="!filteredProjects.length" class="empty">
          <div>ไม่พบ project ที่ตรงกับ filter</div>
          <button v-if="filterActive" class="link-btn" @click="clearFilters">Clear filters</button>
        </div>
      </div>

      <div v-if="filterActive" class="footer">
        Showing <b>{{ filteredProjects.length }}</b> of {{ store.all.length }}
        <button class="link-btn" @click="clearFilters">× Clear all</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.switcher {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--muted);
  position: relative;
}

/* Trigger */
.trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font: inherit;
  font-size: 12.5px;
  padding: 4px 10px;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  background: var(--card);
  color: var(--text);
  max-width: 280px;
  cursor: pointer;
  transition: border-color var(--duration-fast) var(--ease),
              background var(--duration-fast) var(--ease);
}
.trigger:hover { border-color: var(--primary); }
.trigger.open  { border-color: var(--primary); background: var(--primary-soft); }
.trigger.has-filter { border-color: var(--primary); }

.trig-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 220px;
}
.filter-dot {
  font-size: 8px;
  color: var(--primary);
  margin-left: 2px;
}
.trig-caret { font-size: 10px; color: var(--muted); margin-left: 2px; }
.loading    { font-size: 12px; color: var(--muted); }

/* Panel */
.panel {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  z-index: 1000;
  width: 380px;
  max-width: 90vw;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md, 0 8px 24px rgba(0, 0, 0, 0.12));
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  animation: panel-in 160ms var(--ease);
}
@keyframes panel-in {
  from { opacity: 0; transform: translateY(-4px) scale(0.98); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

.search {
  width: 100%;
  font-size: 13px;
  padding: 6px 10px;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  background: var(--bg);
  color: var(--text);
  font-family: inherit;
}
.search:focus { outline: none; border-color: var(--primary); }

.filter-row { display: flex; flex-direction: column; gap: 8px; }
.filter-group { display: flex; flex-direction: column; gap: 4px; }
.filter-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--muted);
  font-weight: 600;
}
.chips { display: flex; flex-wrap: wrap; gap: 4px; }
.chip {
  font: inherit;
  font-size: 11px;
  padding: 3px 9px;
  border-radius: var(--radius-md);
  background: var(--bg);
  border: 1px solid var(--border-soft);
  color: var(--text-secondary, var(--text));
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease);
}
.chip:hover { border-color: var(--primary); }
.chip.active {
  background: var(--primary);
  color: white;
  border-color: var(--primary);
  font-weight: 600;
}
/* "Other" chip — slight visual distinction from real values */
.chip.chip-other {
  font-style: italic;
  color: var(--muted);
}
.chip.chip-other.active {
  background: var(--text-secondary, var(--muted));
  color: var(--card);
  font-style: normal;
}

.no-tax {
  font-size: 11.5px;
  color: var(--muted);
  background: var(--bg);
  border: 1px dashed var(--border-soft);
  border-radius: var(--radius-sm);
  padding: 6px 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}
.no-tax code {
  background: var(--card);
  padding: 1px 5px;
  border-radius: var(--radius-xs);
  font-size: 10.5px;
}
.no-tax a { color: var(--primary); }

/* Project list */
.proj-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 320px;
  overflow-y: auto;
  border-top: 1px solid var(--border-soft);
  padding-top: 6px;
}
.proj-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border: none;
  background: transparent;
  border-radius: var(--radius-sm);
  font: inherit;
  font-size: 12.5px;
  color: var(--text);
  cursor: pointer;
  text-align: left;
  transition: background var(--duration-fast) var(--ease);
}
.proj-row:hover { background: var(--bg); }
.proj-row.current { background: var(--primary-soft); font-weight: 600; }

.proj-dot { font-size: 11px; flex-shrink: 0; }
.proj-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.proj-tag {
  font-size: 10.5px;
  background: var(--bg);
  border: 1px solid var(--border-soft);
  color: var(--muted);
  padding: 1px 6px;
  border-radius: var(--radius-md);
  white-space: nowrap;
}
.proj-row.current .proj-tag { background: var(--card); }
.proj-mark {
  color: var(--primary);
  font-weight: 700;
  margin-left: auto;
}

.empty {
  text-align: center;
  padding: 20px 8px;
  color: var(--muted);
  font-size: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: center;
}

.footer {
  font-size: 11px;
  color: var(--muted);
  border-top: 1px solid var(--border-soft);
  padding-top: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.link-btn {
  background: none;
  border: none;
  color: var(--primary);
  cursor: pointer;
  font: inherit;
  font-size: 11.5px;
  padding: 0;
  margin-left: auto;
}
.link-btn:hover { text-decoration: underline; }
</style>
