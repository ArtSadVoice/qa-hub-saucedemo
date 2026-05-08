/**
 * One-shot Playwright script to capture demo screenshots used by SLIDES.html.
 *
 * Skipped unless CAPTURE_DEMO=1 is set, so it does not run in CI or under
 * `npm test`. To regenerate screenshots locally:
 *
 *   ./setup.ps1                                  # starts hub at :8080
 *   $env:CAPTURE_DEMO = "1"
 *   cd projects/saucedemo
 *   npx playwright test tests/e2e/_capture_demo_screenshots.spec.ts --workers=1
 *
 * Output: docs/screenshots/*.png
 */
import { test } from "@playwright/test";
import * as path from "path";

const HUB = process.env.HUB_URL ?? "http://localhost:8080";
const OUT = path.resolve(__dirname, "../../../../docs/screenshots");

test.use({ viewport: { width: 1440, height: 900 } });

test.beforeEach(() => {
  test.skip(
    process.env.CAPTURE_DEMO !== "1",
    "demo capture only — set CAPTURE_DEMO=1 and start the hub at :8080"
  );
});

async function gotoTab(page: any, selector: string) {
  await page.goto(HUB);
  await page.waitForLoadState("networkidle");
  const link = page.locator(selector).first();
  if (await link.count() > 0) {
    await link.click().catch(() => {});
    await page.waitForTimeout(900);
  }
}

test("capture: 01 dashboard", async ({ page }) => {
  await page.goto(HUB);
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: path.join(OUT, "01-dashboard.png"), fullPage: true });
});

test("capture: 02 pipeline", async ({ page }) => {
  await gotoTab(page, '.nav-item:has-text("Pipeline")');
  await page.screenshot({ path: path.join(OUT, "02-pipeline.png"), fullPage: true });
});

test("capture: 03 bugs", async ({ page }) => {
  await gotoTab(page, '.nav-item:has-text("Bug")');
  await page.screenshot({ path: path.join(OUT, "03-bugs.png"), fullPage: true });
});

test("capture: 04 release-gate", async ({ page }) => {
  await gotoTab(page, '.nav-item:has-text("Release")');
  await page.screenshot({ path: path.join(OUT, "04-release-gate.png"), fullPage: true });
});

test("capture: 05 schedule", async ({ page }) => {
  await gotoTab(page, '.nav-item:has-text("Schedule")');
  await page.screenshot({ path: path.join(OUT, "05-schedule.png"), fullPage: true });
});

test("capture: 06 user-guide", async ({ page }) => {
  await gotoTab(page, '.nav-item:has-text("User Guide")');
  await page.screenshot({ path: path.join(OUT, "06-user-guide.png"), fullPage: true });
});

test("capture: 07 saucedemo home", async ({ page }) => {
  await page.goto("https://www.saucedemo.com/");
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: path.join(OUT, "07-saucedemo-home.png"), fullPage: true });
});

test("capture: 08 saucedemo inventory", async ({ page }) => {
  await page.goto("https://www.saucedemo.com/");
  await page.locator("[data-test='username']").fill("standard_user");
  await page.locator("[data-test='password']").fill("secret_sauce");
  await page.locator("[data-test='login-button']").click();
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: path.join(OUT, "08-saucedemo-inventory.png"), fullPage: true });
});
