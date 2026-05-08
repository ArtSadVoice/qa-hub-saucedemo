/**
 * Lightweight cron parser — enough for the Schedule view's "next 5 fires"
 * preview. Standard 5-field syntax: `minute hour dom month dow`.
 *
 * Supported per field:
 *   *           wildcard
 *   N           literal value
 *   N,M,K       comma list
 *   A-B         inclusive range
 *   * /S        every S (step)
 *   A-B/S       step over range
 *
 * NOT supported (would grow this file 3x without much added value):
 *   • named months (jan, feb, …) / days (mon, tue, …)
 *   • special strings (@hourly, @daily, @reboot)
 *   • seconds (6th field) or year (7th field)
 *
 * If parseCron returns null the caller should fall back to "—" — e.g.
 * the Schedule UI shows "cron: <expr>" without a relative time.
 */

interface CronFields {
  minute: number[]   // 0..59
  hour:   number[]   // 0..23
  dom:    number[]   // 1..31
  month:  number[]   // 1..12
  dow:    number[]   // 0..6 (Sun..Sat — matches JavaScript Date.getDay)
}

const RANGES: Record<keyof CronFields, [number, number]> = {
  minute: [0, 59],
  hour:   [0, 23],
  dom:    [1, 31],
  month:  [1, 12],
  dow:    [0, 6],
}

function parseField(raw: string, field: keyof CronFields): number[] | null {
  const [lo, hi] = RANGES[field]
  const out = new Set<number>()
  for (const part of raw.split(',')) {
    let step = 1
    let body = part
    const slash = part.indexOf('/')
    if (slash >= 0) {
      const s = parseInt(part.slice(slash + 1), 10)
      if (isNaN(s) || s <= 0) return null
      step = s
      body = part.slice(0, slash)
    }
    let from: number, to: number
    if (body === '*') {
      from = lo; to = hi
    } else if (body.includes('-')) {
      const [a, b] = body.split('-').map((s) => parseInt(s, 10))
      if (isNaN(a) || isNaN(b)) return null
      from = a; to = b
    } else {
      const v = parseInt(body, 10)
      if (isNaN(v)) return null
      from = v; to = v
    }
    if (from < lo || to > hi || from > to) return null
    for (let v = from; v <= to; v += step) out.add(v)
  }
  return Array.from(out).sort((a, b) => a - b)
}

export function parseCron(expr: string): CronFields | null {
  const parts = (expr || '').trim().split(/\s+/)
  if (parts.length !== 5) return null
  const minute = parseField(parts[0], 'minute');  if (!minute) return null
  const hour   = parseField(parts[1], 'hour');    if (!hour)   return null
  const dom    = parseField(parts[2], 'dom');     if (!dom)    return null
  const month  = parseField(parts[3], 'month');   if (!month)  return null
  const dow    = parseField(parts[4], 'dow');     if (!dow)    return null
  return { minute, hour, dom, month, dow }
}

/**
 * Find the next N occurrences after `from`. Walks minute-by-minute up to a
 * 4-year safety bound — covers leap years and any reasonably-pathological
 * cron spec without spinning forever on something like "0 0 31 2 *" (Feb 31,
 * never matches → returns less than N entries instead of hanging).
 */
export function nextOccurrences(expr: string, from: Date = new Date(), count: number = 5): Date[] {
  const fields = parseCron(expr)
  if (!fields) return []

  // Vixie cron semantics: if BOTH dom and dow are restricted (not * full set),
  // a date matches if either one matches. Detect "restricted" by comparing
  // length to the full range.
  const domFullSize = RANGES.dom[1] - RANGES.dom[0] + 1
  const dowFullSize = RANGES.dow[1] - RANGES.dow[0] + 1
  const domRestricted = fields.dom.length < domFullSize
  const dowRestricted = fields.dow.length < dowFullSize

  const minSet   = new Set(fields.minute)
  const hourSet  = new Set(fields.hour)
  const monthSet = new Set(fields.month)
  const domSet   = new Set(fields.dom)
  const dowSet   = new Set(fields.dow)

  const results: Date[] = []
  // Start at the next whole minute > from
  const cursor = new Date(from)
  cursor.setSeconds(0, 0)
  cursor.setMinutes(cursor.getMinutes() + 1)

  // Hard upper bound: ~4 years of minutes
  const MAX_ITER = 4 * 366 * 24 * 60
  for (let i = 0; i < MAX_ITER && results.length < count; i++) {
    const m = cursor.getMinutes()
    const h = cursor.getHours()
    const day = cursor.getDate()
    const mon = cursor.getMonth() + 1
    const dow = cursor.getDay()

    const monthOk = monthSet.has(mon)
    const minHourOk = minSet.has(m) && hourSet.has(h)
    let dayOk: boolean
    if (domRestricted && dowRestricted) {
      dayOk = domSet.has(day) || dowSet.has(dow)
    } else {
      dayOk = domSet.has(day) && dowSet.has(dow)
    }

    if (monthOk && dayOk && minHourOk) {
      results.push(new Date(cursor))
    }
    cursor.setMinutes(cursor.getMinutes() + 1)
  }
  return results
}
