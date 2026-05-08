/**
 * scaffold-drift.spec.ts — drift badge renders on the /v2/projects page.
 *
 * Mirrors the "Drift badge (/v2/projects)" scenario in docs/SMOKE_TEST.md.
 * Promoted to checked-in spec because the drift badge is part of a release-
 * blocking decision (operators rely on it to know whether project folders
 * have stale infrastructure files) and was manually smoked every v2.7.x PR.
 *
 * What this test deliberately does NOT assert:
 *   - Exact drift count    — varies with _mock-full state
 *   - Badge colour class   — varies with count (warn vs err)
 */
import { test, expect } from '@playwright/test'

test.beforeEach(async ({ context }) => {
  await context.addInitScript(() => {
    localStorage.setItem('fp_project', '_mock-full')
    localStorage.setItem('fp_onboarding', JSON.stringify({ welcomeSeen: true, tipsSeen: {} }))
  })
})

test('projects page renders a drift badge on the _mock-full card', async ({ page }) => {
  await page.goto('/v2/projects')
  await page.waitForLoadState('networkidle')

  // The _mock-full card must be visible
  const card = page.locator('.proj-card').filter({ hasText: '_mock-full' })
  await expect(card).toBeVisible()

  // A .status-pill carrying "in sync" or "N drift" must appear.
  // Drift data loads asynchronously from /api/scaffold/drift — extend timeout.
  const driftBadge = card.locator('.status-pill').filter({ hasText: /(in sync|drift)/i })
  await expect(driftBadge).toBeVisible({ timeout: 12_000 })
})
