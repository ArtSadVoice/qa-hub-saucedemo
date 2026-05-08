import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: 'tests/e2e',
  testMatch: ['**/*.spec.ts'],
  timeout: 45_000,
  reporter: [['html', { outputFolder: 'playwright-report', open: 'never' }]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:8082',
    headless: true,
  },
  workers: 1,
  webServer: {
    command: 'python -X utf8 app.py --port 8082',
    url: 'http://127.0.0.1:8082/',
    timeout: 20_000,
    // In local dev reuse an existing hub instance; in CI always start fresh.
    reuseExistingServer: !process.env.CI,
  },
})
