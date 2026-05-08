/**
 * useScaffoldDrift — composable that loads scaffold drift status for all
 * projects and exposes per-project lookups + a refresh action.
 *
 * Drift = the project's copy of canonical infrastructure files (preflight
 * helpers, hooks, validated template) doesn't match scaffold/<flavor>/.
 * We surface this so operators can spot stale projects from the dashboard
 * and trigger a sync without diffing by hand.
 *
 * Single shared instance per page (module-level state) so a project list
 * and a project detail view show the same numbers without re-fetching.
 */
import { ref, computed } from 'vue'
import { apiCall } from '@/api/client'
import type { DriftReport } from '@/api/types'

const reports = ref<Record<string, DriftReport>>({})
const loading = ref(false)
let initialLoad: Promise<void> | null = null

async function loadAll(silent = true): Promise<void> {
  loading.value = true
  try {
    const list = await apiCall<DriftReport[]>('/api/scaffold/drift', { silent })
    const next: Record<string, DriftReport> = {}
    for (const r of list || []) {
      if (r.id) next[r.id] = r
    }
    reports.value = next
  } finally {
    loading.value = false
  }
}

export function useScaffoldDrift() {
  if (!initialLoad) initialLoad = loadAll().catch(() => {/* surfaced via toast */})

  function reportFor(pid: string): DriftReport | undefined {
    return reports.value[pid]
  }

  function badgeFor(pid: string): {
    show: boolean
    label: string
    cls: 'ok' | 'warn' | 'err'
    title: string
  } {
    const r = reports.value[pid]
    if (!r) return { show: false, label: '', cls: 'ok', title: '' }
    if (!r.project_exists) return { show: false, label: '', cls: 'ok', title: '' }
    const s = r.summary
    const drift = s.drifted + s.missing_in_project
    if (drift === 0) {
      return {
        show: true, label: '✓ in sync', cls: 'ok',
        title: 'All canonical infrastructure files match scaffold',
      }
    }
    const cls = drift >= 3 ? 'err' : 'warn'
    const parts = []
    if (s.drifted) parts.push(`${s.drifted} drifted`)
    if (s.missing_in_project) parts.push(`${s.missing_in_project} missing`)
    return {
      show: true,
      label: `↻ ${drift} drift`,
      cls,
      title: `Out of sync vs scaffold/${r.project_type}: ${parts.join(', ')}`,
    }
  }

  return {
    reports: computed(() => reports.value),
    loading: computed(() => loading.value),
    reportFor,
    badgeFor,
    refresh: () => loadAll(false),
  }
}
