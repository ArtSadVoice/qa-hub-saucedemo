/**
 * Tiny toast composable — produces the same UX as static/app.js showToast()
 * but driven by Vue reactivity. Used by apiCall() for unified error display.
 */
import { reactive } from 'vue'

export type ToastLevel = 'ok' | 'info' | 'warn' | 'err'

interface ToastEntry {
  id: number
  msg: string
  level: ToastLevel
}

const state = reactive<{ list: ToastEntry[] }>({ list: [] })
let nextId = 1

function show(msg: string, level: ToastLevel = 'ok', duration = 5000) {
  const id = nextId++
  state.list.push({ id, msg, level })
  setTimeout(() => {
    const i = state.list.findIndex((t) => t.id === id)
    if (i >= 0) state.list.splice(i, 1)
  }, duration)
}

function dismiss(id: number) {
  const i = state.list.findIndex((t) => t.id === id)
  if (i >= 0) state.list.splice(i, 1)
}

export function useToast() {
  return { state, show, dismiss }
}
