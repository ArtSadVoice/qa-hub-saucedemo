/**
 * Pinia store for project list + currently-active project.
 * Mirrors the vanilla `currentProject` + `allProjects` globals from app.js,
 * but reactive — every component that reads `current` updates automatically.
 *
 * Persists `current` to localStorage under the same key the legacy UI uses
 * ("fp_project") so both UIs share the same selection.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiCall } from '@/api/client'
import type { Project } from '@/api/types'

const LS_KEY = 'fp_project'

export const useProjectStore = defineStore('projects', () => {
  const all = ref<Project[]>([])
  const current = ref<string>(localStorage.getItem(LS_KEY) || '')
  const loading = ref(false)

  const currentMeta = computed<Project | undefined>(() =>
    all.value.find((p) => p.id === current.value)
  )

  async function load() {
    loading.value = true
    try {
      all.value = (await apiCall<Project[]>('/api/projects')) || []
      // Restore last-used project, or default to first available
      if (!current.value || !all.value.find((p) => p.id === current.value)) {
        if (all.value.length) select(all.value[0].id)
      }
    } finally {
      loading.value = false
    }
  }

  function select(id: string) {
    current.value = id
    localStorage.setItem(LS_KEY, id)
  }

  return { all, current, currentMeta, loading, load, select }
})
