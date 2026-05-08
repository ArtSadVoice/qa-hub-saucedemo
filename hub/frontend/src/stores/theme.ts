/**
 * Theme store — light/dark/system. Persists to localStorage and applies
 * `data-theme` attribute on <html> so CSS variables can swap.
 */
import { defineStore } from 'pinia'
import { ref, watchEffect } from 'vue'

export type Theme = 'light' | 'dark' | 'system'
const LS_KEY = 'fp_theme'

function systemPrefersDark(): boolean {
  return typeof window !== 'undefined'
    && window.matchMedia?.('(prefers-color-scheme: dark)').matches
}

function resolveEffective(theme: Theme): 'light' | 'dark' {
  if (theme === 'system') return systemPrefersDark() ? 'dark' : 'light'
  return theme
}

export const useThemeStore = defineStore('theme', () => {
  const theme = ref<Theme>((localStorage.getItem(LS_KEY) as Theme) || 'system')

  function set(t: Theme) {
    theme.value = t
    localStorage.setItem(LS_KEY, t)
  }

  function toggle() {
    // Cycle: light → dark → system → light
    const next: Theme = theme.value === 'light' ? 'dark'
                     : theme.value === 'dark' ? 'system'
                     : 'light'
    set(next)
  }

  // Apply to <html data-theme="...">
  watchEffect(() => {
    const effective = resolveEffective(theme.value)
    document.documentElement.setAttribute('data-theme', effective)
  })

  // Listen for OS changes when in 'system' mode
  if (typeof window !== 'undefined' && window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (theme.value === 'system') {
        document.documentElement.setAttribute('data-theme', resolveEffective(theme.value))
      }
    })
  }

  return { theme, set, toggle }
})
