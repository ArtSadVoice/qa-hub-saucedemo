/**
 * Bugs store — fetches bug list for the active project + tracks open count
 * for the sidebar badge. Auto-reloads on project switch.
 */
import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { apiCall } from '@/api/client'
import { useProjectStore } from './projects'
import type { Bug } from '@/api/types'

export const useBugsStore = defineStore('bugs', () => {
  const bugs = ref<Bug[]>([])
  const loading = ref(false)

  const openCount = computed(() =>
    bugs.value.filter((b) => b.status === 'Open').length
  )
  const criticalOpenCount = computed(() =>
    bugs.value.filter((b) => b.status === 'Open' && b.severity === 'Critical').length
  )

  async function load() {
    const projects = useProjectStore()
    if (!projects.current) { bugs.value = []; return }
    loading.value = true
    try {
      bugs.value = (await apiCall<Bug[]>(`/api/bugs?p=${projects.current}`, { silent: true })) || []
    } catch {
      bugs.value = []
    } finally {
      loading.value = false
    }
  }

  // Auto-reload when project switches
  const projects = useProjectStore()
  watch(() => projects.current, load, { immediate: true })

  return { bugs, loading, openCount, criticalOpenCount, load }
})
