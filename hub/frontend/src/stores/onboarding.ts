/**
 * Onboarding state — tracks which guides the user has seen.
 * Used by the welcome wizard + per-tab tip banners.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

const LS_KEY = 'fp_onboarding'

interface OnboardingState {
  welcomeSeen: boolean
  tipsSeen: Record<string, boolean>   // per-tab dismissable tips
}

const defaults: OnboardingState = { welcomeSeen: false, tipsSeen: {} }

function loadFromStorage(): OnboardingState {
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (!raw) return { ...defaults }
    return { ...defaults, ...JSON.parse(raw) }
  } catch {
    return { ...defaults }
  }
}

function persist(s: OnboardingState) {
  try { localStorage.setItem(LS_KEY, JSON.stringify(s)) } catch { /* localStorage might be disabled */ }
}

export const useOnboardingStore = defineStore('onboarding', () => {
  const state = ref<OnboardingState>(loadFromStorage())

  function markWelcomeSeen() {
    state.value.welcomeSeen = true
    persist(state.value)
  }

  function dismissTip(id: string) {
    state.value.tipsSeen[id] = true
    persist(state.value)
  }

  function isTipSeen(id: string): boolean {
    return !!state.value.tipsSeen[id]
  }

  function reset() {
    state.value = { ...defaults }
    persist(state.value)
  }

  return { state, markWelcomeSeen, dismissTip, isTipSeen, reset }
})
