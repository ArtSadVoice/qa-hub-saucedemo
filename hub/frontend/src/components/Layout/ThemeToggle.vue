<script setup lang="ts">
import { useThemeStore } from '@/stores/theme'

const theme = useThemeStore()

const labels = { light: '☀️ Light', dark: '🌙 Dark', system: '🖥️ System' }
const tooltips = {
  light:  'Light theme · click for Dark',
  dark:   'Dark theme · click for System',
  system: 'System theme · click for Light',
}
</script>

<template>
  <button class="theme-btn" @click="theme.toggle()" :title="tooltips[theme.theme]" :aria-label="`Theme: ${theme.theme}, click to cycle`">
    <span class="ico">{{ labels[theme.theme].slice(0, 2) }}</span>
  </button>
</template>

<style scoped>
.theme-btn {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 8px;
  cursor: pointer;
  font-size: 14px;
  transition: background .15s;
}
.theme-btn:hover { background: var(--bg); }
</style>
