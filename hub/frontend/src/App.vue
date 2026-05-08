<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Sidebar from '@/components/Layout/Sidebar.vue'
import Topbar from '@/components/Layout/Topbar.vue'
import ShortcutHelpModal from '@/components/ShortcutHelpModal.vue'
import OnboardingWelcome from '@/components/OnboardingWelcome.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { useKeyboardShortcuts } from '@/composables/useKeyboardShortcuts'

const route = useRoute()
const router = useRouter()
const showHelp = ref(false)
const drawerOpen = ref(false)

const { start, stop } = useKeyboardShortcuts(router, () => { showHelp.value = true })

// Close drawer when navigating
watch(() => route.path, () => { drawerOpen.value = false })

onMounted(start)
onUnmounted(stop)
</script>

<template>
  <button class="drawer-toggle" @click="drawerOpen = !drawerOpen" :aria-label="drawerOpen ? 'Close menu' : 'Open menu'">
    <span class="hamburger" :class="{ open: drawerOpen }"></span>
  </button>
  <div v-if="drawerOpen" class="drawer-overlay" @click="drawerOpen = false"></div>
  <Sidebar :class="{ open: drawerOpen }" />
  <main class="main">
    <Topbar />
    <div class="content">
      <RouterView />
    </div>
  </main>
  <ShortcutHelpModal :open="showHelp" @close="showHelp = false" />
  <OnboardingWelcome />
  <ConfirmDialog />
</template>

<style>
.drawer-toggle {
  display: none;
  position: fixed;
  top: 12px;
  left: 12px;
  z-index: 30;
  width: 40px; height: 40px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  cursor: pointer;
  align-items: center;
  justify-content: center;
}
.hamburger,
.hamburger::before,
.hamburger::after {
  display: block;
  width: 18px; height: 2px;
  background: var(--text);
  border-radius: 2px;
  transition: transform var(--duration) var(--ease);
}
.hamburger { position: relative; }
.hamburger::before, .hamburger::after { content: ''; position: absolute; left: 0; }
.hamburger::before { top: -6px; }
.hamburger::after  { top: 6px; }
.hamburger.open { background: transparent; }
.hamburger.open::before { transform: rotate(45deg) translate(4px, 4px); }
.hamburger.open::after  { transform: rotate(-45deg) translate(4px, -4px); }

.drawer-overlay {
  display: none;
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 19;
}

/* Mobile drawer kicks in only on real phone widths.
   iPad portrait (768px) and above keeps the sidebar visible. */
@media (max-width: 640px) {
  .drawer-toggle { display: flex; }
  .drawer-overlay { display: block; }
  .sidebar {
    transform: translateX(-100%);
    transition: transform var(--duration) var(--ease);
  }
  .sidebar.open { transform: translateX(0); box-shadow: var(--shadow-lg); }
  .main { margin-left: 0 !important; }
  .content { padding: var(--space-3) var(--space-4) !important; }
  .topbar h1 { font-size: 16px !important; }
}

/* Tablet — narrower sidebar but still visible */
@media (min-width: 641px) and (max-width: 900px) {
  .sidebar { width: 200px; }
  .main { margin-left: 200px; }
}
</style>

<style>
.main {
  margin-left: 240px;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  /* Critical: prevent main from overflowing horizontally on wide screens */
  min-width: 0;
}
.content {
  padding: var(--space-6);
  flex: 1;
  width: 100%;
  /* No max-width — let content fill the screen on desktop.
     Cards inside auto-wrap their grids. */
}
</style>
