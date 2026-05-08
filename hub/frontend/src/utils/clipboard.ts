/**
 * Copy text to clipboard with a legacy fallback.
 *
 * Why this exists: navigator.clipboard.writeText() throws in real-world
 * scenarios that don't reproduce in headless tests:
 *   - "Document is not focused" — DevTools or another window has focus
 *     when the user clicks. Most common cause of intermittent failures.
 *   - Permission denied (rare on localhost; common on cross-origin iframes)
 *   - Iframe without allow="clipboard-write"
 *   - Non-secure HTTP context (we're on localhost so usually safe)
 *
 * Strategy:
 *   1. Try the async Clipboard API. Works in 95% of cases.
 *   2. If that throws, fall back to a hidden <textarea> + execCommand('copy').
 *      This legacy path tolerates not-focused-document because the textarea
 *      itself receives focus during the copy.
 *   3. Return true on success, false if everything failed. Caller can then
 *      surface the text inline so the user can copy it manually.
 */
export async function copyTextWithFallback(text: string): Promise<boolean> {
  // Method 1: modern Clipboard API
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      // fall through to legacy
    }
  }

  // Method 2: legacy execCommand via off-screen textarea
  if (typeof document === 'undefined') return false
  const ta = document.createElement('textarea')
  ta.value = text
  ta.setAttribute('readonly', '')
  ta.style.position = 'fixed'
  ta.style.top = '0'
  ta.style.left = '0'
  ta.style.opacity = '0'
  ta.style.pointerEvents = 'none'
  document.body.appendChild(ta)
  try {
    ta.focus()
    ta.select()
    ta.setSelectionRange(0, text.length)
    return document.execCommand('copy')
  } catch {
    return false
  } finally {
    document.body.removeChild(ta)
  }
}
