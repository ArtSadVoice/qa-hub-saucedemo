import { Page, expect } from '@playwright/test'
import { BASE_URL, Q_TEXT, TEST_DATA } from '../constants'

/**
 * Page Object Model — {{PROJECT_NAME}}
 *
 * Update methods below to match your app's UI.
 */
export class SurveyPage {
  constructor(readonly page: Page) {}

  async goto() {
    await this.page.goto(BASE_URL)
  }

  async screenshot(tcid: string) {
    await this.page.screenshot({ path: `screenshots/${tcid}.png` })
  }
}
