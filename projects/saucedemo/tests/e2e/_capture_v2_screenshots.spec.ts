/**
 * Capture screenshots of the Vue v2 hub UI (mounted at /v2/).
 *
 * Skipped unless CAPTURE_DEMO=1, same gate as the legacy capture spec.
 *
 *   ./setup.ps1                                  # starts hub at :8080
 *   $env:CAPTURE_DEMO = "1"
 *   cd projects/saucedemo
 *   npx playwright test tests/e2e/_capture_v2_screenshots.spec.ts --workers=1
 *
 * Output: docs/screenshots/v2-*.png
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

async function gotoV2(page: any, route: string) {
  // Origin-set first so localStorage persists, then deep-link to the route.
  // Vue router uses createWebHistory('/v2/'), so route paths are plain
  // (/v2/dashboard, /v2/bugs, ...), no hash.
  await page.goto(`${HUB}/v2/`);
  await page.evaluate(() => {
    localStorage.setItem(
      "fp_onboarding",
      JSON.stringify({ welcomeSeen: true, tipsSeen: {} })
    );
  });
  await page.goto(`${HUB}/v2${route}`);
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1000);
}

test("v2 capture: 01 dashboard", async ({ page }) => {
  await gotoV2(page, "/dashboard");
  await page.screenshot({ path: path.join(OUT, "v2-01-dashboard.png"), fullPage: true });
});

test("v2 capture: 02 overview", async ({ page }) => {
  await gotoV2(page, "/overview");
  await page.screenshot({ path: path.join(OUT, "v2-02-overview.png"), fullPage: true });
});

test("v2 capture: 03 pipeline", async ({ page }) => {
  await gotoV2(page, "/pipeline");
  await page.screenshot({ path: path.join(OUT, "v2-03-pipeline.png"), fullPage: true });
});

test("v2 capture: 04 bugs", async ({ page }) => {
  await gotoV2(page, "/bugs");
  await page.screenshot({ path: path.join(OUT, "v2-04-bugs.png"), fullPage: true });
});

test("v2 capture: 05 release", async ({ page }) => {
  await gotoV2(page, "/release");
  await page.screenshot({ path: path.join(OUT, "v2-05-release.png"), fullPage: true });
});

test("v2 capture: 06 schedule", async ({ page }) => {
  await gotoV2(page, "/schedule");
  await page.screenshot({ path: path.join(OUT, "v2-06-schedule.png"), fullPage: true });
});

test("v2 capture: 07 activity", async ({ page }) => {
  await gotoV2(page, "/activity");
  await page.screenshot({ path: path.join(OUT, "v2-07-activity.png"), fullPage: true });
});

test("v2 capture: 08 guide", async ({ page }) => {
  await gotoV2(page, "/guide");
  await page.screenshot({ path: path.join(OUT, "v2-08-guide.png"), fullPage: true });
});

test("v2 capture: 09 settings", async ({ page }) => {
  await gotoV2(page, "/settings");
  await page.screenshot({ path: path.join(OUT, "v2-09-settings.png"), fullPage: true });
});
