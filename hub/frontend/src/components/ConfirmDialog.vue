<script setup lang="ts">
import { useConfirm } from '@/composables/useConfirm'
import Modal from '@/components/ui/Modal.vue'

const { state, _resolve } = useConfirm()
</script>

<template>
  <Modal :open="state.open" :title="state.title" @close="_resolve(false)">
    <div class="confirm-body">
      <div class="confirm-icon" :class="{ danger: state.danger }">{{ state.icon }}</div>
      <div v-if="state.desc" class="confirm-desc" v-html="state.desc"></div>
    </div>
    <div class="confirm-actions">
      <button class="btn" @click="_resolve(false)">{{ state.cancelLabel }}</button>
      <button class="btn"
              :class="state.danger ? 'btn-danger-solid' : 'btn-primary'"
              @click="_resolve(true)">
        {{ state.okLabel }}
      </button>
    </div>
  </Modal>
</template>

<style scoped>
.confirm-body { display: flex; flex-direction: column; align-items: center; padding: 8px 0 16px; }
.confirm-icon {
  font-size: 42px;
  margin-bottom: 12px;
  width: 64px; height: 64px;
  display: flex; align-items: center; justify-content: center;
  background: var(--warn-soft);
  border-radius: 50%;
}
.confirm-icon.danger { background: var(--danger-soft); }
.confirm-desc {
  text-align: center;
  font-size: 13.5px;
  color: var(--text-secondary);
  line-height: 1.6;
  max-width: 360px;
}
.confirm-actions { display: flex; gap: 8px; justify-content: flex-end; }
.btn-danger-solid {
  background: var(--danger);
  color: white;
  border-color: var(--danger);
}
.btn-danger-solid:hover { background: var(--danger); border-color: var(--danger); }
</style>
