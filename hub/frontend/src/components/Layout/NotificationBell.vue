<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useNotificationsStore } from '@/stores/notifications'

const store = useNotificationsStore()
const open = ref(false)

function toggle() {
  open.value = !open.value
  if (open.value) store.markAllRead()
}

function statusColor(s: string): string {
  const v = s.toLowerCase()
  if (v.startsWith('ok'))    return 'var(--success)'
  if (v.startsWith('error')) return 'var(--danger)'
  return 'var(--warn)'
}

function onClickOutside(e: MouseEvent) {
  if (open.value && !(e.target as HTMLElement).closest('.notif-wrap')) open.value = false
}

onMounted(() => {
  store.startPolling()
  document.addEventListener('click', onClickOutside)
})
onUnmounted(() => document.removeEventListener('click', onClickOutside))
</script>

<template>
  <div class="notif-wrap">
    <button class="bell" @click="toggle" :title="`${store.unreadCount} unread notifications`" aria-label="Notifications">
      🔔
      <span v-if="store.unreadCount > 0" class="badge">{{ store.unreadCount }}</span>
    </button>

    <div v-if="open" class="panel">
      <div class="panel-header">
        🔔 Notifications
        <button v-if="store.items.length" class="clear-btn" @click="store.clear()">Clear all</button>
      </div>
      <div v-if="!store.items.length" class="empty">
        ไม่มี notification ใหม่
      </div>
      <div v-else class="items">
        <div v-for="(it, i) in store.items" :key="i" class="item">
          <div class="status-bar" :style="{ background: statusColor(it.status) }"></div>
          <div class="body">
            <div class="title">
              <b>{{ it.project_id }}</b>
              <span class="action">{{ it.action }}{{ it.tag ? ` ${it.tag}` : '' }}</span>
              <span v-if="it.env === 'prod'" class="env-prod">🔴 PROD</span>
            </div>
            <div class="meta">{{ it.status }} · {{ it.ts }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.notif-wrap { position: relative; }
.bell {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 14px;
  cursor: pointer;
  position: relative;
  color: var(--text);
}
.bell:hover { background: var(--bg); }
.badge {
  position: absolute;
  top: -4px;
  right: -4px;
  background: var(--danger);
  color: white;
  font-size: 9px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 8px;
  min-width: 16px;
  text-align: center;
}
.panel {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  width: 360px;
  max-height: 480px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, .16);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  z-index: 100;
}
.panel-header {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  font-weight: 700;
  font-size: 13px;
  color: var(--text);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.clear-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 11px;
  color: var(--muted);
}
.empty { padding: 30px; text-align: center; color: var(--muted); font-style: italic; font-size: 13px; }
.items { overflow-y: auto; }
.item {
  display: flex;
  border-bottom: 1px solid var(--border);
}
.item:last-child { border-bottom: none; }
.status-bar { width: 4px; flex-shrink: 0; }
.body { padding: 10px 12px; flex: 1; min-width: 0; }
.title { font-size: 12.5px; color: var(--text); display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.action { color: var(--muted); }
.env-prod { background: var(--danger); color: white; padding: 1px 5px; border-radius: 8px; font-size: 9.5px; font-weight: 700; }
.meta { font-size: 11px; color: var(--muted); margin-top: 2px; }
</style>
