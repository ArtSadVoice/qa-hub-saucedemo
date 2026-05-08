<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { apiCall } from '@/api/client'
import { useToast } from '@/composables/useToast'
import type { Bug, Severity, BugStatus } from '@/api/types'
import Modal from '@/components/ui/Modal.vue'
import ScreenshotPicker from '@/components/ScreenshotPicker.vue'

const showPicker = ref(false)

function attachScreenshot(md: string) {
  // Append screenshot markdown to description
  form.description = form.description
    ? form.description.trimEnd() + '\n\n' + md
    : md
}

const props = defineProps<{ bug: Bug | null; projectId: string }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'saved'): void }>()

const SEVERITIES: Severity[] = ['Critical', 'High', 'Medium', 'Low']
const STATUSES: BugStatus[]  = ['Open', 'Fixed', 'Closed']

const toast = useToast()
const form = reactive({
  title: '',
  severity: 'Medium' as Severity,
  status: 'Open' as BugStatus,
  description: '',
  assignee: '',
})

// Declared up-front because the immediate-mode watch below clears it on
// every prop change. Putting it after the watch hits a temporal dead zone
// the first time the modal mounts.
interface TriageSuggestion {
  severity: Severity
  severity_reason: string
  tags: string[]
  similar: string[]
  provider: string
}
const aiSuggestion = ref<TriageSuggestion | null>(null)
const aiLoading = ref(false)

// Sync form whenever bug prop changes (modal opens with new bug)
watch(() => props.bug, (b) => {
  if (b) {
    form.title       = b.title
    form.severity    = b.severity
    form.status      = b.status
    form.description = b.description || ''
    form.assignee    = b.assignee    || ''
  }
  // Clear AI suggestions when switching bugs — they're context-specific
  aiSuggestion.value = null
}, { immediate: true })

async function save() {
  if (!props.bug || !form.title.trim()) return
  try {
    await apiCall('/api/bugs/update', {
      body: {
        project_id: props.projectId,
        id: props.bug.id,
        title:       form.title.trim(),
        severity:    form.severity,
        status:      form.status,
        description: form.description,
        assignee:    form.assignee,
      },
    })
    toast.show('Bug updated', 'ok')
    emit('saved')
    emit('close')
  } catch {
    /* apiCall toasted */
  }
}

// ── A1 Sprint I — AI bug triage ────────────────────────────────────────
async function aiTriage() {
  if (!form.title.trim()) {
    toast.show('Title ก่อน — AI ใช้ title + description ในการ triage', 'warn')
    return
  }
  aiLoading.value = true
  try {
    const r = await apiCall<TriageSuggestion>('/api/ai/bug-triage', {
      silent: true,
      body: {
        project_id:  props.projectId,
        title:       form.title.trim(),
        description: form.description.trim(),
      },
    })
    aiSuggestion.value = r
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : 'failed'
    toast.show(`AI triage failed: ${msg}`, 'err')
  } finally {
    aiLoading.value = false
  }
}

function applySuggestionSeverity() {
  if (!aiSuggestion.value) return
  form.severity = aiSuggestion.value.severity
  toast.show(`✓ Severity → ${aiSuggestion.value.severity}`, 'ok')
}

function applySuggestionTags() {
  if (!aiSuggestion.value || !aiSuggestion.value.tags.length) return
  const tagLine = `\n\nTags: ${aiSuggestion.value.tags.map((t) => `#${t}`).join(' ')}`
  if (!form.description.includes(tagLine.trim())) {
    form.description = form.description.trimEnd() + tagLine
    toast.show('✓ Tags appended to description', 'ok')
  }
}
</script>

<template>
  <Modal :open="!!bug" :title="bug ? `Edit Bug — ${bug.id}` : ''" @close="emit('close')">
    <div v-if="bug" class="form">
      <div class="row">
        <label>Title</label>
        <input v-model="form.title" />
      </div>
      <div class="row two-col">
        <div>
          <label>Severity</label>
          <select v-model="form.severity">
            <option v-for="s in SEVERITIES" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
        <div>
          <label>Status</label>
          <select v-model="form.status">
            <option v-for="s in STATUSES" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
      </div>
      <div class="row">
        <label>Assignee (optional)</label>
        <input v-model="form.assignee" placeholder="email or name" />
      </div>
      <div class="row">
        <label class="desc-label">
          Description (optional)
          <button type="button" class="btn btn-sm pill" @click="showPicker = true">
            📷 Attach screenshot
          </button>
          <button type="button" class="btn btn-sm pill ai-btn" :disabled="aiLoading" @click="aiTriage"
                  title="ส่ง title+description ให้ AI ช่วย triage">
            {{ aiLoading ? '⏳' : '🤖' }} AI Triage
          </button>
        </label>
        <textarea v-model="form.description" rows="5"
                  placeholder="Reproduction steps, expected vs actual…&#10;&#10;Tip: คลิก '🤖 AI Triage' ให้ AI ช่วยเดา severity + tags + similar bugs" />
      </div>

      <!-- AI suggestion panel -->
      <div v-if="aiSuggestion" class="ai-panel">
        <div class="ai-head">
          <span>🤖 AI suggestion</span>
          <span class="ai-prov">via {{ aiSuggestion.provider }}</span>
        </div>
        <div class="ai-row">
          <div class="ai-label">Severity:</div>
          <div class="ai-val">
            <span class="sev-badge" :class="`sev-${aiSuggestion.severity}`">{{ aiSuggestion.severity }}</span>
            <button v-if="aiSuggestion.severity !== form.severity" class="apply-btn"
                    @click="applySuggestionSeverity">
              ↳ Apply
            </button>
            <span v-else class="apply-applied">already set</span>
          </div>
        </div>
        <div v-if="aiSuggestion.severity_reason" class="ai-reason">
          {{ aiSuggestion.severity_reason }}
        </div>
        <div v-if="aiSuggestion.tags.length" class="ai-row">
          <div class="ai-label">Tags:</div>
          <div class="ai-val">
            <span v-for="t in aiSuggestion.tags" :key="t" class="tag-chip">#{{ t }}</span>
            <button class="apply-btn" @click="applySuggestionTags">↳ Append to description</button>
          </div>
        </div>
        <div v-if="aiSuggestion.similar.length" class="ai-row">
          <div class="ai-label">Similar bugs:</div>
          <div class="ai-val">
            <span v-for="id in aiSuggestion.similar" :key="id" class="tag-chip dup">⚠ {{ id }}</span>
            <span class="ai-hint">— ตรวจก่อน save เผื่อ duplicate</span>
          </div>
        </div>
      </div>

      <div class="actions">
        <button class="btn" @click="emit('close')">Cancel</button>
        <button class="btn btn-primary" @click="save" :disabled="!form.title.trim()">💾 Save</button>
      </div>
    </div>
  </Modal>

  <ScreenshotPicker :open="showPicker" @close="showPicker = false" @pick="attachScreenshot" />
</template>

<style scoped>
.form { display: flex; flex-direction: column; gap: 12px; }
.row label { display: block; font-size: 11px; color: var(--muted); margin-bottom: 4px; font-weight: 600; }
.row input, .row select, .row textarea { width: 100%; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 8px; }

.desc-label { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.btn-sm.pill { padding: 2px 8px; font-size: 11px; }

.ai-btn {
  background: var(--primary-soft);
  color: var(--primary-dk, var(--primary));
  border: 1px solid rgba(0, 113, 227, 0.3);
}
.ai-btn:hover:not(:disabled) {
  background: var(--primary);
  color: white;
  border-color: var(--primary);
}

/* AI suggestion panel */
.ai-panel {
  background: var(--primary-soft);
  border: 1px solid rgba(0, 113, 227, 0.25);
  border-radius: var(--radius-sm);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ai-head {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 700;
  color: var(--primary-dk, var(--primary));
  letter-spacing: -0.01em;
}
.ai-prov { font-size: 10.5px; font-weight: 500; opacity: 0.75; font-family: "SF Mono", monospace; }
.ai-row {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  font-size: 12.5px;
}
.ai-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  color: var(--muted);
  font-weight: 600;
  min-width: 90px;
}
.ai-val { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.ai-reason {
  font-size: 11.5px;
  color: var(--text-secondary, var(--text));
  font-style: italic;
  margin-left: 100px;
  margin-top: -4px;
  line-height: 1.5;
}
.ai-hint { font-size: 11px; color: var(--muted); }

.sev-badge {
  font-size: 10.5px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 10px;
}
.sev-badge.sev-Critical { background: var(--danger);       color: white; }
.sev-badge.sev-High     { background: var(--danger-soft);  color: var(--danger); }
.sev-badge.sev-Medium   { background: var(--warn-soft);    color: var(--warn); }
.sev-badge.sev-Low      { background: var(--success-soft); color: var(--success); }

.tag-chip {
  font-size: 11px;
  background: var(--card);
  border: 1px solid var(--border-soft);
  color: var(--text-secondary, var(--text));
  padding: 1px 8px;
  border-radius: var(--radius-md);
  font-family: "SF Mono", monospace;
}
.tag-chip.dup { color: var(--warn); border-color: rgba(255, 159, 10, 0.3); }

.apply-btn {
  font-family: inherit;
  font-size: 11px;
  background: transparent;
  border: 1px dashed var(--primary);
  color: var(--primary);
  padding: 2px 9px;
  border-radius: var(--radius-xs);
  cursor: pointer;
  font-weight: 600;
}
.apply-btn:hover { background: var(--primary); color: white; border-style: solid; }
.apply-applied { font-size: 11px; color: var(--muted); font-style: italic; }
</style>
