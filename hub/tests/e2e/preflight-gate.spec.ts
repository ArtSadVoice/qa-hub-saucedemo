/**
 * preflight-gate.spec.ts — locked Excel file triggers Preflight failed modal.
 *
 * Mirrors the "Preflight gate (/v2/pipeline)" scenario in docs/SMOKE_TEST.md.
 * Promoted to checked-in spec because a regression here would let pipelines
 * run against locked/corrupted Excel files — a hard-to-recover production
 * failure.
 *
 * Cleanup: the planted lock file is removed in a finally block so a test
 * failure or early interruption doesn't leave stale state. CI also re-seeds
 * _mock-full/input fresh each run.
 */
import { test, expect } from '@playwright/test'
import path from 'path'
import fs from 'fs/promises'

// _mock-full lives one level above the repo root.
// CI seeding:  `cd .. && mkdir -p _mock-full/input ...`  (parent of repo)
// Local layout: C:\Automation\_mock-full\input\
const MOCK_FULL_INPUT = path.join(__dirname, '..', '..', '..', '_mock-full', 'input')
const LOCK_FILE = path.join(MOCK_FULL_INPUT, '~$ci_test.xlsx')

test.beforeEach(async ({ context }) => {
  await context.addInitScript(() => {
    localStorage.setItem('fp_project', '_mock-full')
    localStorage.setItem('fp_onboarding', JSON.stringify({ welcomeSeen: true, tipsSeen: {} }))
  })
})

test('pipeline run is blocked by Preflight failed modal when Excel lock is present', async ({ page }) => {
  // Plant a fake Excel lock — mimics the ~$filename.xlsx Windows creates when
  // a file is open in Excel.
  await fs.writeFile(LOCK_FILE, '')

  try {
    await page.goto('/v2/pipeline')
    await page.waitForLoadState('networkidle')

    // Click the first stage ▶ Run button.
    // runStage() always calls runPreflight() before executing the stage endpoint.
    const runBtn = page
      .locator('.stage-actions button')
      .filter({ hasText: '▶ Run' })
      .first()
    await expect(runBtn).toBeEnabled()
    await runBtn.click()

    // Preflight failed modal must appear
    const modal = page.locator('[role="dialog"]')
    await expect(modal).toBeVisible({ timeout: 10_000 })
    await expect(modal.locator('.modal-header h3')).toContainText('Preflight failed')

    // Modal body must name the planted lock file
    await expect(modal.locator('.modal-body')).toContainText('~$ci_test.xlsx')

    // Click ยกเลิก (Cancel) — pipeline must not start
    await modal.locator('button').filter({ hasText: 'ยกเลิก' }).click()
    await expect(modal).not.toBeVisible()
  } finally {
    await fs.unlink(LOCK_FILE).catch(() => { /* already removed or never created */ })
  }
})
