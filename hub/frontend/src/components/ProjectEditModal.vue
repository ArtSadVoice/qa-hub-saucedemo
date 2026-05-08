<script setup lang="ts">
import { reactive, watch } from 'vue'
import { apiCall } from '@/api/client'
import { useToast } from '@/composables/useToast'
import { useProjectStore } from '@/stores/projects'
import type { Project } from '@/api/types'
import Modal from '@/components/ui/Modal.vue'

const props = defineProps<{ project: Project | null }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'saved'): void }>()

const toast = useToast()
const projects = useProjectStore()

const form = reactive({
  name:      '',
  color:     '#0071E3',
  type:      'full-pipeline' as Project['type'],
  phase:     'active' as NonNullable<Project['phase']>,
  figma_url: '',
  company:   '',
  category:  '',
})

watch(() => props.project, (p) => {
  if (p) {
    form.name      = p.name
    form.color     = p.color || '#0071E3'
    form.type      = p.type
    form.phase     = (p.phase as typeof form.phase) || 'active'
    form.figma_url = p.figma_url || ''
    form.company   = p.company || ''
    form.category  = p.category || ''
  }
}, { immediate: true })

async function save() {
  if (!props.project || !form.name.trim()) return
  try {
    await apiCall('/api/projects/update', {
      body: {
        id:        props.project.id,
        name:      form.name.trim(),
        color:     form.color,
        type:      form.type,
        phase:     form.phase,
        figma_url: form.figma_url.trim(),
        company:   form.company.trim(),
        category:  form.category.trim(),
      },
    })
    toast.show('Project updated', 'ok')
    await projects.load()
    emit('saved')
    emit('close')
  } catch { /* apiCall toasted */ }
}
</script>

<template>
  <Modal :open="!!project" :title="project ? `Edit Project — ${project.id}` : ''" @close="emit('close')">
    <div v-if="project" class="form">
      <div class="row">
        <label>Display Name</label>
        <input v-model="form.name" />
      </div>
      <div class="row two-col">
        <div>
          <label>Type</label>
          <select v-model="form.type">
            <option value="full-pipeline">full-pipeline</option>
            <option value="manual-testing">manual-testing</option>
            <option value="playwright-only">playwright-only</option>
            <option value="pytest-only">pytest-only</option>
          </select>
        </div>
        <div>
          <label>Phase</label>
          <select v-model="form.phase">
            <option value="active">🟢 active</option>
            <option value="planning">🟡 planning</option>
            <option value="paused">⚪ paused</option>
          </select>
          <div class="phase-hint">
            <span v-if="form.phase === 'active'">Project ดำเนินการอยู่ — Release Gate ใช้งานปกติ</span>
            <span v-else-if="form.phase === 'planning'">ยังไม่เริ่มเขียน test — Release Gate ข้าม (SKIP_PLANNING)</span>
            <span v-else>หยุดพัฒนา — Release Gate ข้าม (SKIP_PAUSED)</span>
          </div>
        </div>
      </div>
      <div class="row two-col">
        <div>
          <label>Color</label>
          <div style="display:flex;gap:6px">
            <input v-model="form.color" type="color" style="width:50px;padding:2px" />
            <input v-model="form.color" type="text" placeholder="#0071E3" />
          </div>
        </div>
        <div>
          <label>Figma URL (optional)</label>
          <input v-model="form.figma_url" type="text" placeholder="https://figma.com/…" />
        </div>
      </div>
      <div class="row two-col">
        <div>
          <label>Company (optional)</label>
          <input v-model="form.company" type="text" placeholder="Acme Corp" />
        </div>
        <div>
          <label>Category (optional)</label>
          <input v-model="form.category" type="text" placeholder="QA · Survey · Internal …" />
        </div>
      </div>
      <div class="hint">
        ID, path, และ folder structure เปลี่ยนใน v2 ยังไม่ได้ — ใช้ legacy /projects ถ้าต้องเปลี่ยน
      </div>
      <div class="actions">
        <button class="btn" @click="emit('close')">Cancel</button>
        <button class="btn btn-primary" @click="save" :disabled="!form.name.trim()">💾 Save</button>
      </div>
    </div>
  </Modal>
</template>

<style scoped>
.form { display: flex; flex-direction: column; gap: 12px; }
.row label {
  display: block;
  font-size: 11px;
  color: var(--muted);
  margin-bottom: 4px;
  font-weight: 600;
}
.row input, .row select { width: 100%; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 8px; }
.hint {
  font-size: 11.5px;
  color: var(--muted);
  margin-top: 4px;
}
.phase-hint {
  font-size: 11px;
  color: var(--muted);
  margin-top: 4px;
  line-height: 1.4;
  min-height: 14px;
}
</style>
