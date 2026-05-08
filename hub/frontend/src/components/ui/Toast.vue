<script setup lang="ts">
import { useToast } from '@/composables/useToast'

const { state, dismiss } = useToast()
</script>

<template>
  <div class="toast-stack">
    <div v-for="t in state.list" :key="t.id" class="toast" :class="`toast-${t.level}`">
      <span style="flex:1">{{ t.msg }}</span>
      <button class="dismiss" @click="dismiss(t.id)">&times;</button>
    </div>
  </div>
</template>

<style scoped>
.toast-stack {
  position: fixed;
  bottom: 20px;
  right: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 9999;
}
.toast {
  background: white;
  border: 1px solid var(--border);
  border-left-width: 4px;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 240px;
  box-shadow: 0 4px 12px rgba(0,0,0,.08);
  animation: slidein .24s ease-out;
}
.toast-ok   { border-left-color: var(--success); }
.toast-info { border-left-color: #2E75B6; }  /* stylelint-disable-line color-no-hex */
.toast-warn { border-left-color: var(--warn); }
.toast-err  { border-left-color: var(--danger); }
.dismiss {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 16px;
  color: var(--muted);
  padding: 0 4px;
}
@keyframes slidein {
  from { opacity: 0; transform: translateX(20px); }
  to   { opacity: 1; transform: translateX(0); }
}
</style>
