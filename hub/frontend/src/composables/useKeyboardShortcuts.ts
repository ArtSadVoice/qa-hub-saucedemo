/**
 * Global keyboard shortcuts.
 *
 * Single key:
 *   ?       show help modal
 *   Esc     close any open modal/palette (handled by individual components)
 *
 * Sequence (g + letter, vim-style — type 'g' then any letter within 1.2s):
 *   g d     dashboard
 *   g o     overview
 *   g p     pipeline
 *   g r     release gate
 *   g s     schedule
 *   g b     bugs
 *   g a     activity feed
 *   g t     settings
 *
 * Listeners are attached on mount (App.vue) and stop firing inside <input>
 * / <textarea> / contenteditable to avoid hijacking text input.
 */
import { ref } from 'vue'
import type { Router } from 'vue-router'

export function useKeyboardShortcuts(router: Router, showHelp: () => void) {
  const lastKeyTime = ref(0)
  const lastKey = ref('')

  function inEditable(target: EventTarget | null): boolean {
    if (!(target instanceof HTMLElement)) return false
    const tag = target.tagName.toLowerCase()
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return true
    if (target.isContentEditable) return true
    return false
  }

  function handler(e: KeyboardEvent) {
    if (inEditable(e.target)) return
    if (e.ctrlKey || e.metaKey || e.altKey) return  // Don't intercept system shortcuts

    const now = Date.now()
    const within = now - lastKeyTime.value < 1200

    // Single-key shortcuts
    if (e.key === '?') { e.preventDefault(); showHelp(); return }

    // Two-key sequences starting with 'g'
    if (lastKey.value === 'g' && within) {
      const map: Record<string, string> = {
        d: '/dashboard', o: '/overview', p: '/pipeline', r: '/release',
        s: '/schedule', b: '/bugs', a: '/activity', t: '/settings',
        i: '/input', u: '/output', c: '/screenshots', y: '/syscheck',
        h: '/guide', j: '/projects',
      }
      const path = map[e.key.toLowerCase()]
      if (path) {
        e.preventDefault()
        router.push(path)
        lastKey.value = ''
        return
      }
    }

    if (e.key.toLowerCase() === 'g') {
      lastKey.value = 'g'
      lastKeyTime.value = now
    } else {
      lastKey.value = ''
    }
  }

  function start() { window.addEventListener('keydown', handler) }
  function stop()  { window.removeEventListener('keydown', handler) }

  return { start, stop }
}

export const SHORTCUT_HELP = [
  { keys: '?',     desc: 'Show this help' },
  { keys: 'Esc',   desc: 'Close any modal or palette' },
  { keys: 'Ctrl+K', desc: 'Open command palette' },
  { keys: '',      desc: '' },  // separator
  { keys: 'g d',   desc: 'Go to Dashboard' },
  { keys: 'g o',   desc: 'Go to All Projects Overview' },
  { keys: 'g p',   desc: 'Go to Pipeline' },
  { keys: 'g r',   desc: 'Go to Release Gate' },
  { keys: 'g s',   desc: 'Go to Schedule' },
  { keys: 'g b',   desc: 'Go to Bug Tracker' },
  { keys: 'g a',   desc: 'Go to Activity Feed' },
  { keys: 'g j',   desc: 'Go to Projects' },
  { keys: 'g t',   desc: 'Go to Settings' },
  { keys: 'g i',   desc: 'Go to Input' },
  { keys: 'g u',   desc: 'Go to Output' },
  { keys: 'g c',   desc: 'Go to Screenshots' },
  { keys: 'g y',   desc: 'Go to System Check' },
  { keys: 'g h',   desc: 'Go to User Guide' },
]
