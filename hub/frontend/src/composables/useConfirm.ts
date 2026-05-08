/**
 * Promise-based confirm dialog — replaces window.confirm() with a styled
 * modal that can show context (description, danger flag, custom labels).
 *
 * Usage:
 *   const ok = await confirm({ title: 'Delete bug?', danger: true })
 *   if (!ok) return
 */
import { reactive } from 'vue'

export interface ConfirmOptions {
  title?: string
  desc?: string
  icon?: string
  okLabel?: string
  cancelLabel?: string
  danger?: boolean
}

interface ConfirmState extends ConfirmOptions {
  open: boolean
  resolver: ((ok: boolean) => void) | null
}

const state = reactive<ConfirmState>({
  open: false,
  resolver: null,
  title: 'Confirm',
  desc: '',
  icon: '⚠️',
  okLabel: 'OK',
  cancelLabel: 'Cancel',
  danger: false,
})

export function useConfirm() {
  function confirm(opts: ConfirmOptions = {}): Promise<boolean> {
    return new Promise<boolean>((resolve) => {
      state.title       = opts.title       ?? 'Confirm'
      state.desc        = opts.desc        ?? ''
      state.icon        = opts.icon        ?? (opts.danger ? '🚨' : '⚠️')
      state.okLabel     = opts.okLabel     ?? 'OK'
      state.cancelLabel = opts.cancelLabel ?? 'Cancel'
      state.danger      = opts.danger      ?? false
      state.open        = true
      state.resolver    = resolve
    })
  }

  function _resolve(ok: boolean) {
    state.open = false
    if (state.resolver) state.resolver(ok)
    state.resolver = null
  }

  return { state, confirm, _resolve }
}
