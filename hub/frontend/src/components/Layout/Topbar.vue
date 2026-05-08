<script setup lang="ts">
import { useRoute } from 'vue-router'
import Toast from '@/components/ui/Toast.vue'
import ProjectSwitcher from '@/components/Layout/ProjectSwitcher.vue'
import ThemeToggle from '@/components/Layout/ThemeToggle.vue'
import NotificationBell from '@/components/Layout/NotificationBell.vue'
import CommandPalette from '@/components/CommandPalette.vue'
import { ref, onMounted, onUnmounted } from 'vue'

const route = useRoute()
const cmdOpen = ref(false)

function onKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    cmdOpen.value = true
  }
}
onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="topbar">
    <h1>{{ (route.meta.title as string) || 'QA Hub Demo' }}</h1>
    <ProjectSwitcher />
    <div class="topbar-actions">
      <button class="topbar-btn" @click="cmdOpen = true" title="Command palette (Ctrl+K)" aria-label="Command palette">⌘K</button>
      <NotificationBell />
      <ThemeToggle />
      <span class="badge">v2</span>
    </div>
  </div>
  <Toast />
  <CommandPalette v-model="cmdOpen" />
</template>

<style scoped>
.topbar-actions { display: flex; gap: 6px; align-items: center; margin-left: 12px; }
.topbar-btn {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 8px;
  cursor: pointer;
  font-size: 12px;
  font-family: inherit;
  color: var(--text);
}
.topbar-btn:hover { background: var(--bg); }
</style>

<style scoped>
.topbar {
  background: white;
  border-bottom: 1px solid var(--border);
  padding: 13px 24px;
  display: flex;
  align-items: center;
  gap: 10px;
  position: sticky;
  top: 0; z-index: 10;
}
.topbar h1 { font-size: 16px; font-weight: 700; flex: 1; }
.badge {
  background: #DCFCE7;  /* stylelint-disable-line color-no-hex */
  color: #14532d;  /* stylelint-disable-line color-no-hex */
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 700;
}

/* Mobile trim: project pill + v2 badge are non-essential at ≤640.
   The drawer hamburger already exposes the project switcher inside the
   sidebar, and the v2 badge is just dev signaling. */
@media (max-width: 640px) {
  .topbar { padding: 10px 12px; gap: 6px; }
  .topbar h1 {
    font-size: 15px;
    min-width: 0;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    /* leave room for hamburger which is fixed at left:12px */
    margin-left: 44px;
  }
  .topbar :deep(.switcher) { display: none; }
  .topbar .badge { display: none; }
  .topbar-btn,
  .topbar-actions :deep(.bell),
  .topbar-actions :deep(.theme-btn) {
    padding: 8px 10px;
    font-size: 13px;
    min-height: 36px; min-width: 36px;
    display: inline-flex; align-items: center; justify-content: center;
  }
  .topbar-actions { margin-left: auto; gap: 4px; }
}
</style>
