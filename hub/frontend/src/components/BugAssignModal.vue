<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { apiCall } from '@/api/client'
import { useToast } from '@/composables/useToast'
import type { Bug } from '@/api/types'
import Modal from '@/components/ui/Modal.vue'

interface Recipient { name: string; email: string }

const props = defineProps<{ bug: Bug | null; projectId: string }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'saved'): void }>()

const toast = useToast()
const assignee = ref('')
const sendEmail = ref(true)
const recipients = ref<Recipient[]>([])

watch(() => props.bug, (b) => {
  assignee.value = b?.assignee || ''
}, { immediate: true })

onMounted(async () => {
  // Pre-fill recipient list from email config so quick-assign can pick from team
  try {
    const cfg = await apiCall<{ to: Recipient[]; cc: Recipient[] }>('/api/config/email', { silent: true })
    recipients.value = [...(cfg.to || []), ...(cfg.cc || [])]
  } catch { /* no email config — manual entry only */ }
})

function pickRecipient(r: Recipient) {
  assignee.value = r.email
}

async function save() {
  if (!props.bug) return
  try {
    await apiCall('/api/bugs/update', {
      body: {
        project_id: props.projectId,
        id: props.bug.id,
        assignee: assignee.value.trim(),
        notify_assignee: sendEmail.value && !!assignee.value.trim(),
      },
    })
    toast.show(
      assignee.value
        ? `Assigned to ${assignee.value}${sendEmail.value ? ' (email sent)' : ''}`
        : 'Assignment cleared',
      'ok'
    )
    emit('saved')
    emit('close')
  } catch { /* apiCall toasted */ }
}
</script>

<template>
  <Modal :open="!!bug" :title="bug ? `Assign — ${bug.title}` : ''" @close="emit('close')">
    <div v-if="bug" class="form">
      <div class="row">
        <label>Assignee (email or name)</label>
        <input v-model="assignee" placeholder="email@example.com or 'leave blank to unassign'" />
      </div>

      <div v-if="recipients.length" class="quick-list">
        <div class="quick-label">Quick pick from email recipients:</div>
        <div class="chip-row">
          <button v-for="r in recipients" :key="r.email" type="button"
                  class="chip" @click="pickRecipient(r)"
                  :class="{ active: assignee === r.email }">
            {{ r.name || r.email }}
          </button>
        </div>
      </div>

      <div class="row">
        <label class="checkbox">
          <input type="checkbox" v-model="sendEmail" :disabled="!assignee.trim()" />
          <span>Send notification email</span>
        </label>
      </div>

      <div class="actions">
        <button class="btn" @click="emit('close')">Cancel</button>
        <button class="btn btn-primary" @click="save">💾 Assign</button>
      </div>
    </div>
  </Modal>
</template>

<style scoped>
.form { display: flex; flex-direction: column; gap: 14px; }
.row label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; font-weight: 600; }
.row input { width: 100%; }
.checkbox { display: flex; align-items: center; gap: 8px; font-size: 13px; cursor: pointer; }
.checkbox input { width: auto; margin: 0; }
.quick-list { background: var(--bg); border: 1px solid var(--border); border-radius: 7px; padding: 10px 12px; }
.quick-label { font-size: 11px; color: var(--muted); margin-bottom: 6px; font-weight: 600; }
.chip-row { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 3px 10px;
  font-size: 12px;
  cursor: pointer;
  color: var(--text);
}
.chip:hover { border-color: var(--primary); }
.chip.active { background: var(--primary); color: white; border-color: var(--primary); }
.actions { display: flex; gap: 8px; justify-content: flex-end; }
</style>
