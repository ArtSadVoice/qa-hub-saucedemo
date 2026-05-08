<script setup lang="ts">
import { computed } from 'vue'
import { apiCall } from '@/api/client'
import { useToast } from '@/composables/useToast'
import type { Bug, BugStatus } from '@/api/types'

const props = defineProps<{ bugs: Bug[]; projectId: string }>()
const emit = defineEmits<{ (e: 'edit', b: Bug): void; (e: 'changed'): void }>()

const toast = useToast()
const COLUMNS: { status: BugStatus; label: string; icon: string }[] = [
  { status: 'Open',   label: 'Open',   icon: '🟠' },
  { status: 'Fixed',  label: 'Fixed',  icon: '🟢' },
  { status: 'Closed', label: 'Closed', icon: '⚪' },
]

const grouped = computed(() => {
  const g: Record<BugStatus, Bug[]> = { Open: [], Fixed: [], Closed: [] }
  for (const b of props.bugs) g[b.status].push(b)
  return g
})

const sevColor = (s: string) => ({
  Critical: 'var(--danger)',
  High:     '#FF6B5C',
  Medium:   'var(--warn)',
  Low:      'var(--success)',
}[s] || 'var(--muted)')

function ageDays(b: Bug): number | null {
  if (!b.created_at) return null
  const t = Date.parse(b.created_at.replace(' ', 'T'))
  return isNaN(t) ? null : Math.floor((Date.now() - t) / 86400000)
}

// Drag and drop
function onDragStart(e: DragEvent, b: Bug) {
  e.dataTransfer?.setData('text/plain', b.id)
  ;(e.target as HTMLElement).classList.add('dragging')
}
function onDragEnd(e: DragEvent) {
  ;(e.target as HTMLElement).classList.remove('dragging')
}
function onDragOver(e: DragEvent) {
  e.preventDefault()
  ;(e.currentTarget as HTMLElement).classList.add('drop-active')
}
function onDragLeave(e: DragEvent) {
  ;(e.currentTarget as HTMLElement).classList.remove('drop-active')
}
async function onDrop(e: DragEvent, newStatus: BugStatus) {
  e.preventDefault()
  ;(e.currentTarget as HTMLElement).classList.remove('drop-active')
  const id = e.dataTransfer?.getData('text/plain')
  if (!id) return
  const bug = props.bugs.find((b) => b.id === id)
  if (!bug || bug.status === newStatus) return
  try {
    await apiCall('/api/bugs/update', { body: { project_id: props.projectId, id, status: newStatus } })
    bug.status = newStatus
    toast.show(`Moved → ${newStatus}`, 'ok')
    emit('changed')
  } catch { /* apiCall toasted */ }
}

// Click to cycle (mobile / no-drag fallback)
async function cycleStatus(b: Bug) {
  const order: BugStatus[] = ['Open', 'Fixed', 'Closed']
  const next = order[(order.indexOf(b.status) + 1) % order.length]
  try {
    await apiCall('/api/bugs/update', { body: { project_id: props.projectId, id: b.id, status: next } })
    b.status = next
    emit('changed')
  } catch {}
}
</script>

<template>
  <div class="kanban">
    <div v-for="col in COLUMNS" :key="col.status"
         class="kb-col"
         @dragover="onDragOver"
         @dragleave="onDragLeave"
         @drop="onDrop($event, col.status)">
      <div class="kb-head">
        <span>{{ col.icon }} {{ col.label }}</span>
        <span class="count">{{ grouped[col.status].length }}</span>
      </div>
      <div class="kb-body">
        <div v-if="!grouped[col.status].length" class="kb-empty">No {{ col.label.toLowerCase() }} bugs</div>
        <div v-for="b in grouped[col.status]" :key="b.id"
             class="bug-card"
             draggable="true"
             @dragstart="onDragStart($event, b)"
             @dragend="onDragEnd"
             @click="emit('edit', b)">
          <div class="bug-card-top">
            <span class="sev-dot" :style="{ background: sevColor(b.severity) }" :title="b.severity"></span>
            <span class="bug-title">{{ b.title }}</span>
          </div>
          <div class="bug-meta">
            <span>{{ b.severity }}</span>
            <span v-if="ageDays(b) !== null" class="age" :class="{ aged: ageDays(b)! >= 7 && b.status === 'Open' }">
              {{ ageDays(b) }}d
            </span>
            <span v-if="b.assignee" class="assignee">👤 {{ b.assignee }}</span>
          </div>
          <button class="cycle" @click.stop="cycleStatus(b)" title="Cycle status">→</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.kanban {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
@media (max-width: 900px) {
  .kanban { grid-template-columns: 1fr; }
}
.kb-col {
  background: var(--bg);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  padding: 12px;
  min-height: 240px;
  transition: background var(--duration-fast) var(--ease),
              border-color var(--duration-fast) var(--ease);
}
.kb-col.drop-active {
  background: var(--primary-soft);
  border-color: var(--primary);
  border-style: dashed;
}
.kb-head {
  display: flex;
  justify-content: space-between;
  font-size: 12.5px;
  font-weight: 700;
  color: var(--text);
  padding: 4px 4px 10px;
  border-bottom: 1px solid var(--border-soft);
  margin-bottom: 10px;
}
.count {
  background: var(--card);
  color: var(--muted);
  padding: 1px 8px;
  border-radius: var(--radius-md);
  font-size: 11px;
}
.kb-body { display: flex; flex-direction: column; gap: 8px; }
.kb-empty { font-size: 12px; color: var(--muted); padding: 12px 8px; text-align: center; }

.bug-card {
  background: var(--card);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  cursor: pointer;
  position: relative;
  box-shadow: var(--shadow-sm);
  transition: transform var(--duration-fast) var(--ease),
              box-shadow var(--duration-fast) var(--ease);
}
.bug-card:hover { transform: translateY(-1px); box-shadow: var(--shadow-md); }
.bug-card.dragging { opacity: 0.4; }
.bug-card-top { display: flex; gap: 8px; align-items: flex-start; margin-bottom: 6px; }
.sev-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; margin-top: 5px; }
.bug-title { font-size: 13px; font-weight: 600; color: var(--text); flex: 1; line-height: 1.4; }
.bug-meta { display: flex; gap: 10px; font-size: 11px; color: var(--muted); flex-wrap: wrap; }
.age { font-weight: 600; }
.age.aged { color: var(--warn); }
.assignee { font-size: 11px; }

.cycle {
  position: absolute;
  top: 6px; right: 6px;
  width: 20px; height: 20px;
  background: var(--bg);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-xs);
  font-size: 10px;
  cursor: pointer;
  opacity: 0;
  transition: opacity var(--duration-fast) var(--ease);
}
.bug-card:hover .cycle { opacity: 1; }
.cycle:hover { background: var(--primary); color: white; border-color: var(--primary); }
</style>
