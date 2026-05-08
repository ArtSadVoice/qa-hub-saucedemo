<script setup lang="ts">
import { watch, onMounted, onUnmounted, nextTick, ref } from 'vue'

const props = defineProps<{ open: boolean; title?: string }>()
const emit = defineEmits<{ (e: 'close'): void }>()
const boxRef = ref<HTMLDivElement | null>(null)

function onBackdropClick() { emit('close') }

function onKey(e: KeyboardEvent) {
  if (props.open && e.key === 'Escape') {
    e.preventDefault()
    emit('close')
  }
}

// Autofocus first focusable element when modal opens
watch(() => props.open, async (open) => {
  if (open) {
    await nextTick()
    const first = boxRef.value?.querySelector<HTMLElement>(
      'input:not([type=hidden]), select, textarea, button:not(.x)'
    )
    first?.focus()
  }
})

onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" class="modal-overlay" @click.self="onBackdropClick">
        <div ref="boxRef" class="modal-box" role="dialog" aria-modal="true">
          <div class="modal-header">
            <h3>{{ title }}</h3>
            <button class="x" @click="emit('close')" aria-label="Close">&times;</button>
          </div>
          <div class="modal-body"><slot /></div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, .45);
  display: flex; align-items: center; justify-content: center;
  z-index: 9990;
  padding: 20px;
}
.modal-box {
  background: white;
  border-radius: 12px;
  width: 480px; max-width: 100%;
  max-height: 88vh; overflow-y: auto;
  box-shadow: 0 16px 48px rgba(0, 0, 0, .25);
}
.modal-header {
  padding: 14px 20px;
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
}
.modal-header h3 { font-size: 15px; color: var(--text); }
.x { background: none; border: none; font-size: 22px; color: var(--muted); cursor: pointer; padding: 0 4px; }
.modal-body { padding: 18px 20px; }

.modal-enter-active, .modal-leave-active { transition: opacity .2s; }
.modal-enter-active .modal-box, .modal-leave-active .modal-box { transition: transform .25s ease-out; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-from .modal-box, .modal-leave-to .modal-box { transform: scale(.95); }
</style>
