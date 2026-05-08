import { test, expect } from "@playwright/test";
import { LoginPage } from "../pages/LoginPage";
import { InventoryPage } from "../pages/InventoryPage";

test.describe("TS_06 — problem_user visual regressions", () => {
  test("TS_06_01 @visual problem_user inventory has broken images", async ({
    page,
  }) => {
    const login = new LoginPage(page);
    await login.goto();
    await login.loginAs("problem");

    const inventory = new InventoryPage(page);
    await inventory.expectLoaded();

    // problem_user serves the same dog image for every product. Capture
    // a full-page screenshot so QA can compare visually run-over-run.
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveScreenshot("problem_user-inventory.png", {
      maxDiffPixelRatio: 0.05,
      fullPage: true,
    });
  });
});
