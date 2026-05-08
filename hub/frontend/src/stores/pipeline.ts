/**
 * Pipeline state store — single source of truth for "is something running?"
 * Surfaced in the topbar Run badge so users see status from any tab.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export type RunState = 'idle' | 'running' | 'success' | 'failed'

export const usePipelineStore = defineStore('pipeline', () => {
  const state = ref<RunState>('idle')
  const stage = ref<string>('')
  const startedAt = ref<number>(0)

  function start(stageId: string) {
    state.value = 'running'
    stage.value = stageId
    startedAt.value = Date.now()
  }

  function finish(success: boolean) {
    state.value = success ? 'success' : 'failed'
    // Auto-clear back to idle after 6 seconds so the badge is informative
    // but doesn't camp on the topbar forever.
    setTimeout(() => {
      if (state.value === 'success' || state.value === 'failed') {
        state.value = 'idle'
        stage.value = ''
      }
    }, 6000)
  }

  function reset() {
    state.value = 'idle'
    stage.value = ''
  }

  const label = computed(() => {
    if (state.value === 'running') return `Running ${stage.value}`
    if (state.value === 'success') return 'Done'
    if (state.value === 'failed')  return 'Failed'
    return 'Ready'
  })

  return { state, stage, startedAt, label, start, finish, reset }
})
