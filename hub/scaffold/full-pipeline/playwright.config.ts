import { defineConfig, devices } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || '{{BASE_URL}}'
const TEST_ENV = (process.env.TEST_ENV || 'uat').toLowerCase()

export default defineConfig({
  testDir: './tests/e2e',
  outputDir: './test-results',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  retries: process.env.CI ? 2 : 1,  // retry 2x ใน CI, 1x local — สำหรับ flaky detection
  workers: 1,
  reporter: [
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['json', { outputFile: 'logs/playwright_results.json' }],
    ['list'],
  ],
  use: {
    baseURL: BASE_URL,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
    locale: 'th-TH',
    timezoneId: 'Asia/Bangkok',
    // TEST_ENV ส่งผ่าน env var — Hub ใช้ค่านี้สำหรับ UAT/Prod switching
    // ดึงใน spec ได้ด้วย process.env.TEST_ENV
  },
  metadata: { env: TEST_ENV },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
