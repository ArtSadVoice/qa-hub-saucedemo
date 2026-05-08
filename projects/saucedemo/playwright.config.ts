import { defineConfig, devices } from "@playwright/test";

/**
 * Hub-compatible Playwright config.
 *
 * `--reporter=list` is what QA Hub Demo's stage-5 runner passes when it
 * spawns `npx playwright test --reporter=list --grep @<tag>`. We add an
 * HTML report on top so users can also browse results locally.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report" }],
    ["junit", { outputFile: "test-results/junit.xml" }],
  ],
  use: {
    baseURL: process.env.BASE_URL ?? "https://www.saucedemo.com",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    viewport: { width: 1280, height: 800 },
    locale: "en-US",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    // Uncomment when wiring the saucedemo-mobile project (phase=planning today)
    // {
    //   name: "mobile-chrome",
    //   testMatch: /.*\.visual\.spec\.ts/,
    //   use: { ...devices["Pixel 7"] },
    // },
  ],
});
