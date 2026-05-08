<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '@/stores/projects'
import { useThemeStore } from '@/stores/theme'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>()

const router = useRouter()
const projects = useProjectStore()
const theme = useThemeStore()

interface Cmd {
  icon: string
  label: string
  desc: string
  action: () => void
  group: string
}

// Helper — push with query, used by Action commands that pre-filter / pre-trigger
// the destination view. Each consumer view reads route.query on mount.
const goWithQuery = (path: string, query: Record<string, string>) => router.push({ path, query })

// Static commands — augmented with one "Switch → <project>" per registered project at runtime.
const staticCmds: Cmd[] = [
  { icon: '🏠', label: 'Dashboard',          desc: 'Go to dashboard',          group: 'Nav', action: () => router.push('/dashboard') },
  { icon: '🌐', label: 'All Projects',       desc: 'Cross-project overview',   group: 'Nav', action: () => router.push('/overview') },
  { icon: '⚙️', label: 'Pipeline',           desc: 'Run pipeline stages',      group: 'Nav', action: () => router.push('/pipeline') },
  { icon: '🚦', label: 'Release Gate',       desc: 'Release readiness',        group: 'Nav', action: () => router.push('/release') },
  { icon: '🐛', label: 'Bug Tracker',        desc: 'Bugs',                     group: 'Nav', action: () => router.push('/bugs') },
  { icon: '📅', label: 'Schedule',           desc: 'Scheduled runs',           group: 'Nav', action: () => router.push('/schedule') },
  { icon: '🗂️', label: 'Projects',           desc: 'Project list + edit',      group: 'Nav', action: () => router.push('/projects') },
  { icon: '📋', label: 'Activity Feed',      desc: 'Audit log',                group: 'Nav', action: () => router.push('/activity') },
  { icon: '🩺', label: 'System Check',       desc: 'Hub health check',         group: 'Nav', action: () => router.push('/syscheck') },
  { icon: '⚙️', label: 'Settings',           desc: 'Branding · Email · AI',    group: 'Nav', action: () => router.push('/settings') },
  { icon: '📖', label: 'User Guide',         desc: 'Help / docs',              group: 'Nav', action: () => router.push('/guide') },

  // ── Quick actions: navigate AND set up the destination view via query params ──
  { icon: '🚨', label: 'Open Critical bugs', desc: 'Bug Tracker filtered to severity=Critical, status=Open',
    group: 'Action', action: () => goWithQuery('/bugs', { severity: 'Critical', status: 'Open' }) },
  { icon: '🟠', label: 'Open all Open bugs', desc: 'Bug Tracker filtered to status=Open across severities',
    group: 'Action', action: () => goWithQuery('/bugs', { status: 'Open' }) },
  { icon: '➕', label: 'Add new bug',         desc: 'Open Bug Tracker with focus on the title input',
    group: 'Action', action: () => goWithQuery('/bugs', { action: 'add' }) },
  { icon: '📤', label: 'Send report',         desc: 'Open Pipeline → Send Report dialog',
    group: 'Action', action: () => goWithQuery('/pipeline', { action: 'send-report' }) },
  { icon: '⚡', label: 'Run all stages',      desc: 'Open Pipeline with confirm to run all stages',
    group: 'Action', action: () => goWithQuery('/pipeline', { action: 'run-all' }) },
  { icon: '🚦', label: 'Re-evaluate Release Gate', desc: 'Refresh release-gate verdict for current project',
    group: 'Action', action: () => goWithQuery('/release', { action: 'reload' }) },
  { icon: '📊', label: 'Hub metrics',         desc: 'Show /api/metrics summary on Overview',
    group: 'Action', action: () => router.push('/overview') },

  { icon: '🌙', label: 'Toggle theme',       desc: 'Cycle light → dark → system', group: 'Action', action: () => theme.toggle() },
  { icon: '🔄', label: 'Refresh page',       desc: 'Reload current view',      group: 'Action', action: () => location.reload() },
  { icon: '🔗', label: 'Open Legacy UI',     desc: 'Switch to vanilla dashboard', group: 'Action', action: () => location.href = '/' },
]

const query = ref('')
const idx = ref(0)
const inputRef = ref<HTMLInputElement | null>(null)

const allCmds = computed<Cmd[]>(() => {
  const projCmds: Cmd[] = projects.all.map((p) => ({
    icon: '📁',
    label: `Switch → ${p.name}`,
    desc:  'Set active project',
    group: 'Project',
    action: () => projects.select(p.id),
  }))
  return [...staticCmds, ...projCmds]
})

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return allCmds.value
  return allCmds.value.filter((c) =>
    (c.label + ' ' + c.desc + ' ' + c.group).toLowerCase().includes(q)
  )
})

watch(filtered, () => { idx.value = 0 })

watch(() => props.modelValue, async (v) => {
  if (v) {
    query.value = ''
    idx.value = 0
    await nextTick()
    inputRef.value?.focus()
  }
})

function exec(c?: Cmd) {
  if (!c && filtered.value.length) c = filtered.value[idx.value]
  if (!c) return
  c.action()
  emit('update:modelValue', false)
}

function onKey(e: KeyboardEvent) {
  if (!props.modelValue) return
  if (e.key === 'Escape') { emit('update:modelValue', false); return }
  if (e.key === 'ArrowDown') { e.preventDefault(); idx.value = Math.min(idx.value + 1, filtered.value.length - 1) }
  if (e.key === 'ArrowUp')   { e.preventDefault(); idx.value = Math.max(idx.value - 1, 0) }
  if (e.key === 'Enter')     { exec() }
}
onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <Teleport to="body">
    <div v-if="modelValue" class="cp-overlay" @click.self="emit('update:modelValue', false)">
      <div class="cp-box">
        <input ref="inputRef" v-model="query" placeholder="Type to search… (↑↓ navigate · Enter select · Esc close)" />
        <div v-if="!filtered.length" class="cp-empty">ไม่พบคำสั่งที่ค้นหา</div>
        <div v-else class="cp-list">
          <div v-for="(c, i) in filtered" :key="i"
               class="cp-item"
               :class="{ active: i === idx }"
               @mouseover="idx = i"
               @click="exec(c)">
            <span class="cp-icon">{{ c.icon }}</span>
            <div class="cp-body">
              <div class="cp-label">{{ c.label }}</div>
              <div class="cp-desc">{{ c.desc }}</div>
            </div>
            <span class="cp-group">{{ c.group }}</span>
          </div>
        </div>
        <div class="cp-footer">
          <span><kbd>↑↓</kbd> navigate</span>
          <span><kbd>Enter</kbd> select</span>
          <span><kbd>Esc</kbd> close</span>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.cp-overlay {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, .45);
  z-index: 99999;
  display: flex;
  justify-content: center;
  padding-top: 14vh;
}
.cp-box {
  width: 600px; max-width: 95vw;
  background: var(--card);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 16px 48px rgba(0, 0, 0, .28);
  display: flex;
  flex-direction: column;
  max-height: 70vh;
}
.cp-box input {
  width: 100%;
  border: none;
  border-bottom: 1px solid var(--border);
  padding: 14px 18px;
  font-size: 14px;
  background: var(--card);
  color: var(--text);
  outline: none;
  font-family: inherit;
}
.cp-empty { padding: 30px; text-align: center; color: var(--muted); font-style: italic; font-size: 13px; }
.cp-list { overflow-y: auto; flex: 1; }
.cp-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 14px;
  cursor: pointer;
  border-bottom: 1px solid var(--border);
}
.cp-item.active { background: var(--bg); }
.cp-icon { font-size: 18px; flex-shrink: 0; width: 24px; text-align: center; }
.cp-body { flex: 1; min-width: 0; }
.cp-label { font-size: 13px; font-weight: 600; color: var(--text); }
.cp-desc { font-size: 11.5px; color: var(--muted); margin-top: 1px; }
.cp-group { font-size: 10px; padding: 2px 7px; background: var(--bg); color: var(--muted); border-radius: 8px; flex-shrink: 0; }
.cp-footer {
  padding: 8px 14px;
  display: flex;
  gap: 14px;
  font-size: 11px;
  color: var(--muted);
  background: var(--bg);
  border-top: 1px solid var(--border);
}
kbd {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 1px 5px;
  font-family: inherit;
  font-size: 10px;
}
</style>
