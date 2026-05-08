<script setup lang="ts">
import Modal from '@/components/ui/Modal.vue'
import { SHORTCUT_HELP } from '@/composables/useKeyboardShortcuts'

defineProps<{ open: boolean }>()
defineEmits<{ (e: 'close'): void }>()
</script>

<template>
  <Modal :open="open" title="⌨️ Keyboard Shortcuts" @close="$emit('close')">
    <div class="shortcuts">
      <div v-for="(s, i) in SHORTCUT_HELP" :key="i">
        <hr v-if="!s.keys" class="sep" />
        <div v-else class="row">
          <kbd v-for="(k, j) in s.keys.split(' ')" :key="j">{{ k }}</kbd>
          <span class="desc">{{ s.desc }}</span>
        </div>
      </div>
    </div>
    <p class="hint">
      Sequences (e.g. <kbd>g</kbd> <kbd>d</kbd>) — type the second key within 1.2 seconds.<br>
      Shortcuts pause while typing in an input field.
    </p>
  </Modal>
</template>

<style scoped>
.shortcuts { display: flex; flex-direction: column; gap: 6px; }
.row { display: flex; align-items: center; gap: 8px; padding: 4px 0; }
kbd {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 1px 8px;
  font-family: 'Cascadia Mono', monospace;
  font-size: 11.5px;
  color: var(--text);
  min-width: 26px;
  text-align: center;
  display: inline-block;
}
.desc { font-size: 13px; color: var(--text); margin-left: auto; }
.sep { border: none; border-top: 1px solid var(--border); margin: 8px 0; }
.hint { font-size: 11.5px; color: var(--muted); margin-top: 16px; line-height: 1.5; }
</style>
