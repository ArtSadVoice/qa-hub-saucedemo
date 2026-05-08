<script setup lang="ts">
import { ref, computed } from 'vue'
import { apiCall } from '@/api/client'
import { useToast } from '@/composables/useToast'
import type { Severity, BugStatus } from '@/api/types'

const props = defineProps<{ failedTests: string[]; projectId: string }>()
const emit = defineEmits<{ (e: 'dismiss'): void; (e: 'logged', count: number): void }>()

const toast = useToast()
const selected = ref<Set<string>>(new Set(props.failedTests))   // pre-select all
const defaultSeverity = ref<Severity>('High')
const submitting = ref(false)

const allSelected = computed(() => selected.value.size === props.failedTests.length)

function toggle(t: string) {
  if (selected.value.has(t)) selected.value.delete(t)
  else selected.value.add(t)
}

function toggleAll() {
  if (allSelected.value) selected.value.clear()
  else props.failedTests.forEach((t) => selected.value.add(t))
}

async function logSelected() {
  if (!selected.value.size) return
  submitting.value = true
  let logged = 0
  try {
    for (const t of selected.value) {
      try {
        await apiCall('/api/bugs/add', {
          silent: true,
          body: {
            project_id: props.projectId,
            title:       `Test failure: ${t}`,
            severity:    defaultSeverity.value,
            status:      'Open' as BugStatus,
            description: `Auto-logged from Stage 5 test run\n\nFailing test: ${t}`,
          },
        })
        logged++
      } catch { /* skip individual failure */ }
    }
    toast.show(`Logged ${logged} bug(s) from failed tests`, 'ok')
    emit('logged', logged)
    emit('dismiss')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="detect-panel">
    <div class="header">
      <span class="icon">🐞</span>
      <div class="text">
        <div class="title">{{ failedTests.length }} test(s) failed — log as bugs?</div>
        <div class="hint">Pre-selected all. Uncheck items you don't want to track.</div>
      </div>
      <button class="btn btn-sm" @click="emit('dismiss')" title="Dismiss">×</button>
    </div>

    <div class="controls">
      <label class="select-all">
        <input type="checkbox" :checked="allSelected" @change="toggleAll">
        <span>Select all ({{ selected.size }} / {{ failedTests.length }})</span>
      </label>
      <label class="severity-pick">
        Severity:
        <select v-model="defaultSeverity">
          <option>Critical</option>
          <option>High</option>
          <option>Medium</option>
          <option>Low</option>
        </select>
      </label>
    </div>

    <ul class="test-list">
      <li v-for="t in failedTests" :key="t">
        <label>
          <input type="checkbox" :checked="selected.has(t)" @change="toggle(t)">
          <code>{{ t }}</code>
        </label>
      </li>
    </ul>

    <div class="actions">
      <button class="btn" @click="emit('dismiss')">Skip</button>
      <button class="btn btn-primary"
              :disabled="!selected.size || submitting"
              :aria-busy="submitting"
              @click="logSelected">
        🐛 Log {{ selected.size }} bug{{ selected.size === 1 ? '' : 's' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.detect-panel {
  background: var(--warn-soft);
  border: 1px solid rgba(255, 159, 10, 0.35);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  margin: var(--space-3) 0;
}
.header { display: flex; align-items: flex-start; gap: var(--space-3); margin-bottom: var(--space-3); }
.icon { font-size: 24px; }
.text { flex: 1; }
.title { font-weight: 700; font-size: 14px; color: var(--warn); }
[data-theme="dark"] .title { color: var(--warn); }
.hint { font-size: 12px; color: var(--muted); margin-top: 2px; }

.controls {
  display: flex;
  gap: var(--space-4);
  align-items: center;
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
}
.select-all, .severity-pick {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  color: var(--text-secondary);
}
.select-all input, .severity-pick input { width: auto; margin: 0; }
.severity-pick select { font-size: 12.5px; padding: 3px 8px; }

.test-list {
  list-style: none;
  max-height: 200px;
  overflow-y: auto;
  background: var(--card);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  padding: 6px;
}
.test-list li label {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 8px;
  font-size: 12.5px;
  cursor: pointer;
  border-radius: var(--radius-xs);
}
.test-list li label:hover { background: var(--bg); }
.test-list code {
  font-family: "SF Mono", monospace;
  font-size: 11.5px;
  flex: 1;
  word-break: break-all;
}

.actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: var(--space-3); }
.btn-sm { padding: 0 10px; font-size: 18px; min-height: 28px; }
</style>
