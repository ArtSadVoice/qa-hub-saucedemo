/**
 * useSSE — minimal Server-Sent Events composable.
 * Used for Pipeline run streams + System Check streams.
 *
 * Returns reactive state {connected, lines, finished, error} plus
 * start/stop methods. Each `data:` event is appended to lines and
 * also passed to the optional onMessage callback for parsing.
 *
 * Stream protocol: Flask sends a final {"done": true, "returncode": N} sentinel
 * on the last `data:` line and then closes the stream. EventSource fires
 * `onerror` in BOTH cases — clean close and real network failure — so we
 * disambiguate by inspecting the last received line.
 */
import { ref, onUnmounted } from 'vue'

export interface SSEHooks {
  onMessage?: (line: string) => void
  onClose?:   () => void
  onError?:   (err: Event) => void
}

function isDoneSentinel(line: string): boolean {
  if (!line) return false
  try {
    const obj = JSON.parse(line)
    return obj && obj.done === true
  } catch {
    return false
  }
}

export function useSSE() {
  const connected = ref(false)
  const finished  = ref(false)
  const error     = ref<string>('')
  const lines     = ref<string[]>([])
  let es: EventSource | null = null

  function start(url: string, hooks: SSEHooks = {}) {
    stop()
    finished.value = false
    error.value = ''
    lines.value = []
    es = new EventSource(url)
    connected.value = true

    es.onmessage = (ev) => {
      const line = ev.data ?? ''
      lines.value.push(line)
      hooks.onMessage?.(line)
    }
    es.onerror = (ev) => {
      const lastLine = lines.value[lines.value.length - 1] || ''
      const cleanClose = isDoneSentinel(lastLine)
      const wasConnecting = es?.readyState === EventSource.CONNECTING

      if (cleanClose) {
        finished.value = true
      } else {
        // Make the failure visible: push a synthetic done-line so the log block
        // shows the error and downstream onClose handlers detect a non-zero rc.
        // wasConnecting = browser was attempting to auto-reconnect → real
        // network drop or server crash. Otherwise, EventSource hit an error
        // before the connection was even established (e.g. 401/404/500).
        const reason = wasConnecting
          ? 'ขาดการเชื่อมต่อกับ server (stream interrupted)'
          : 'เชื่อมต่อ stream ไม่สำเร็จ — ตรวจ network หรือ server logs'
        const synthetic = JSON.stringify({
          line: `❌ ${reason}`,
          type: 'err',
          done: true,
          returncode: -1,
        })
        lines.value.push(synthetic)
        error.value = reason
      }

      connected.value = false
      hooks.onError?.(ev)
      stop()
      hooks.onClose?.()
    }
  }

  function stop() {
    if (es) {
      es.close()
      es = null
    }
    connected.value = false
  }

  onUnmounted(stop)

  return { connected, finished, error, lines, start, stop }
}
