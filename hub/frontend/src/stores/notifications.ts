/**
 * Notifications store — polls /api/schedules/notifications every 60s,
 * keeps unread count + items list. Used by NotificationBell in topbar.
 */
import { defineStore } from 'pinia'
import { ref, onScopeDispose } from 'vue'
import { apiCall } from '@/api/client'

export interface NotifItem {
  ts: string
  project_id: string
  action: string
  tag?: string
  status: string
  env?: string
  icon?: string
}

export const useNotificationsStore = defineStore('notifications', () => {
  const items = ref<NotifItem[]>([])
  const unreadCount = ref(0)
  let pollHandle: ReturnType<typeof setInterval> | null = null

  async function poll() {
    try {
      const newItems = await apiCall<NotifItem[]>('/api/schedules/notifications', { silent: true })
      if (newItems && newItems.length) {
        items.value = [...newItems, ...items.value].slice(0, 50)
        unreadCount.value += newItems.length
      }
    } catch { /* poll failures are fine — Hub may be restarting */ }
  }

  function startPolling() {
    if (pollHandle) return
    poll()  // immediate first call
    pollHandle = setInterval(poll, 60_000)
  }

  function stopPolling() {
    if (pollHandle) { clearInterval(pollHandle); pollHandle = null }
  }

  function markAllRead() {
    unreadCount.value = 0
  }

  function clear() {
    items.value = []
    unreadCount.value = 0
  }

  onScopeDispose(stopPolling)

  return { items, unreadCount, startPolling, stopPolling, markAllRead, clear, poll }
})
