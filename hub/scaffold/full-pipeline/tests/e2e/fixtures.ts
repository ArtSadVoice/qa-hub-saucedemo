import { test as base } from '@playwright/test'
import { SurveyPage } from './pages/SurveyPage'
import * as fs from 'fs'
import * as path from 'path'

/**
 * Custom Playwright fixtures.
 *
 * Import `test` and `expect` from this file (not '@playwright/test')
 * to get `survey` and `td` fixtures injected into every test.
 *
 * Usage:
 *   import { test, expect } from '../fixtures'
 *
 *   test('my test', async ({ survey, td }) => {
 *     await survey.selectNps(td.boundary.nps_min)
 *   })
 */

function loadTestData(): Record<string, any> {
  const dataPath = path.join(__dirname, 'data', 'test-data.json')
  if (!fs.existsSync(dataPath)) return {}
  try {
    return JSON.parse(fs.readFileSync(dataPath, 'utf-8'))
  } catch {
    return {}
  }
}

type SurveyFixtures = {
  survey: SurveyPage
  td: Record<string, any>  // test data จาก data/test-data.json
}

export const test = base.extend<SurveyFixtures>({
  survey: async ({ page }, use) => {
    await use(new SurveyPage(page))
  },
  td: async ({}, use) => {
    await use(loadTestData())
  },
})

export { expect } from '@playwright/test'
