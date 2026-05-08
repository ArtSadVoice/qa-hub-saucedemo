/**
 * sync-flow.spec.ts — Sync now button → confirm modal → success toast.
 *
 * Mirrors the "Sync now button" scenario in docs/SMOKE_TEST.md.
 * Promoted to checked-in spec because a regression here would silently break
 * infrastructure-file propagation to project folders (release-blocking).
 *
 * Skip-if-clean: the sync button only appears when drift is non-zero.
 * In CI _mock-full is seeded without scaffold files so drift is always
 * non-zero. On a fully-synced local workspace the test skips gracefully.
 *
 * Cleanup: CI re-seeds _mock-full fresh each run — synced files don't
 * persist across builds. No explicit restore step needed.
 */
import { test, expect } from '@playwright/test'

test.beforeEach(async ({ context }) => {
  await context.addInitScript(() => {
    localStorage.setItem('fp_project', '_mock-full')
    localStorage.setItem('fp_onboarding', JSON.stringify({ welcomeSeen: true, tipsSeen: {} }))
  })
})

test('sync-now flow shows confirm modal then toasts Synced', async ({ page }) => {
  await page.goto('/v2/projects')
  await page.waitForLoadState('networkidle')

  const card = page.locator('.proj-card').filter({ hasText: '_mock-full' })
  await expect(card).toBeVisible()

  // Wait for drift data to settle (loaded asynchronously from /api/scaffold/drift)
  await card
    .locator('.status-pill')
    .filter({ hasText: /(in sync|drift)/i })
    .waitFor({ timeout: 12_000 })

  // Skip if project is already in sync (sync button only shown on drifted projects)
  const syncBtn = card.locator('button').filter({ hasText: /Sync now/i })
  test.skip(await syncBtn.count() === 0, '_mock-full is already in sync — sync button not shown')

  await syncBtn.click()

  // Confirm modal must appear with title referencing both the action and the project
  const modal = page.locator('[role="dialog"]')
  await expect(modal).toBeVisible()
  const title = modal.locator('.modal-header h3')
  await expect(title).toContainText('Sync')
  await expect(title).toContainText('_mock-full')

  // Click the okLabel button inside the confirm-actions area
  const confirmBtn = modal.locator('.confirm-actions button').filter({ hasText: /Sync now/i })
  await confirmBtn.click()

  // Success toast must appear within 30 s (sync shells out to sync_to_project.py)
  const toast = page.locator('.toast').filter({ hasText: /Synced/i })
  await expect(toast).toBeVisible({ timeout: 30_000 })
})
