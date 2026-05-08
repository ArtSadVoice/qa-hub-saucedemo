/**
 * apiCall — TypeScript port of the vanilla helper in static/app.js.
 * Same contract: throws on non-2xx (with the server's {error, detail} message),
 * auto-toasts via the shared toast composable.
 */
import { useToast } from '@/composables/useToast'

export interface ApiCallOptions {
  method?: string
  body?: unknown
  headers?: Record<string, string>
  silent?: boolean
  raw?: boolean
}

export class ApiError extends Error {
  status?: number
  detail?: string
  network?: boolean
}

export async function apiCall<T = unknown>(url: string, opts: ApiCallOptions = {}): Promise<T> {
  const { body, silent, raw, method, headers = {}, ...rest } = opts
  const init: RequestInit = {
    method: method || (body !== undefined ? 'POST' : 'GET'),
    headers: { ...headers },
    ...rest,
  }
  if (body !== undefined) {
    init.body = typeof body === 'string' ? body : JSON.stringify(body)
    ;(init.headers as Record<string, string>)['Content-Type'] =
      (init.headers as Record<string, string>)['Content-Type'] || 'application/json'
  }

  const toast = useToast()
  let r: Response
  try {
    r = await fetch(url, init)
  } catch (netErr) {
    const msg = netErr instanceof Error ? netErr.message : String(netErr)
    if (!silent) toast.show(`Network error: ${msg}`, 'err')
    const err = new ApiError(msg)
    err.network = true
    throw err
  }

  if (raw) return r as unknown as T

  if (!r.ok) {
    let detail = ''
    try {
      const j = await r.json()
      detail = j.error || j.detail || ''
    } catch {
      /* not JSON */
    }
    const msg = detail || `HTTP ${r.status} on ${url}`
    if (!silent) toast.show(msg, 'err')
    const err = new ApiError(msg)
    err.status = r.status
    err.detail = detail
    throw err
  }

  try {
    return (await r.json()) as T
  } catch {
    return null as unknown as T
  }
}
