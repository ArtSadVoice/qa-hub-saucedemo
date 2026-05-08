// playwright.config.ts
// ตัวอย่าง config สำหรับโปรเจกต์ที่ใช้กับ QA Agentic Loop

import { defineConfig, devices } from '@playwright/test'
import path from 'path'
import dotenv from 'dotenv'

// โหลด .env.test
dotenv.config({ path: '.env.test' })

export default defineConfig({
  testDir: './tests/e2e',

  // Screenshot path — screenshot_injector.py จะหาไฟล์จากที่นี่
  outputDir: './screenshots',

  // Timeouts
  timeout: 30_000,           // 30s per test (local)
  expect: { timeout: 5_000 },

  // Retries
  retries: process.env.CI ? 2 : 0,

  // Parallel
  workers: process.env.CI ? 1 : undefined,

  // Reporter
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['json', { outputFile: 'logs/playwright_results.json' }],
    ['list'],
  ],

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',

    // Screenshot on failure → ชื่อไฟล์ตาม test title (TCID)
    screenshot: 'only-on-failure',
    screenshotPath: ({ testInfo }) => {
      // ดึง TCID จาก test title: "TS_01_01 ตรวจสอบ..."
      const match = testInfo.title.match(/^(TS_\d{2}_\d{2,3})/)
      const tcid  = match ? match[1] : testInfo.title.replace(/\s+/g, '_')
      return path.join('screenshots', `${tcid}.png`)
    },

    video: 'retain-on-failure',
    trace: 'on-first-retry',

    // Locale
    locale: 'th-TH',
    timezoneId: 'Asia/Bangkok',
  },

  projects: [
    // Setup: auth state
    {
      name: 'setup',
      testMatch: /.*\.setup\.ts/,
    },

    // Chrome — main
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
      dependencies: ['setup'],
    },

    // Mobile (TS_07)
    {
      name: 'mobile-chrome',
      use: { ...devices['Pixel 5'] },
      testMatch: /TS_07.*/,
    },
  ],

  // Dev server (optional — comment ออกถ้ารัน server แยก)
  // webServer: {
  //   command: 'npm run dev',
  //   url: process.env.BASE_URL || 'http://localhost:3000',
  //   reuseExistingServer: !process.env.CI,
  // },
})
