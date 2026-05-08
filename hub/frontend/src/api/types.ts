// API response shapes used by the Vue app.
// Mirror the backend (release_gate.py / app.py) so the editor catches drift.

export type Severity = 'Critical' | 'High' | 'Medium' | 'Low'
export type BugStatus = 'Open' | 'Fixed' | 'Closed'

export interface Bug {
  id: string
  title: string
  severity: Severity
  status: BugStatus
  created_at: string
  description?: string
  assignee?: string
}

export interface Project {
  id: string
  name: string
  path: string
  type: 'full-pipeline' | 'manual-testing' | 'playwright-only' | 'pytest-only'
  phase?: 'active' | 'planning' | 'paused'
  color?: string
  figma_url?: string
  company?: string
  category?: string
  // Enriched fields populated by /api/projects (server reads disk on each request)
  exists?: boolean
  has_xlsx?: boolean
  has_docx?: boolean
  screenshot_count?: number
  last_run?: string | null
}

export interface ToastKind {
  level: 'ok' | 'info' | 'warn' | 'err'
}

// /api/scaffold/drift[/<pid>] response shape — see scaffold_audit.py
export type DriftFileStatus =
  | 'current' | 'drifted' | 'missing-in-project' | 'missing-in-scaffold'

export interface DriftFile {
  rel: string
  status: DriftFileStatus
  project_hash: string
  scaffold_hash: string
}

export interface DriftSummary {
  current: number
  drifted: number
  missing_in_project: number
  missing_in_scaffold: number
}

export interface DriftReport {
  project_path: string
  scaffold_path: string
  project_type: string
  files: DriftFile[]
  summary: DriftSummary
  ok: boolean
  // Only present in /api/scaffold/drift (all projects)
  id?: string
  name?: string
  project_exists?: boolean
}

// /api/preflight/<pid> response shape — see scaffold_audit.py
export interface PreflightTemplate {
  path: string
  exists: boolean
  issues: string[]
}

export interface PreflightReport {
  project_path: string
  project_exists: boolean
  ok: boolean
  excel_locks: string[]
  template: PreflightTemplate
  summary: string
}

// /api/scaffold/sync/<pid> response shape
export interface SyncResult {
  ok: boolean
  stdout: string
  stderr: string
  returncode: number
}
