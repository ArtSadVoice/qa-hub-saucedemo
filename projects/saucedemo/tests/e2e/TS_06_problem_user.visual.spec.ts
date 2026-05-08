import { test, expect } from "@playwright/test";
import * as path from "path";
import { LoginPage } from "../pages/LoginPage";
import { InventoryPage } from "../pages/InventoryPage";

test.describe("TS_06 — problem_user visual regressions", () => {
  test("TS_06_01 @visual problem_user serves the same broken image for every product", async ({
    page,
  }) => {
    const login = new LoginPage(page);
    await login.goto();
    await login.loginAs("problem");

    const inventory = new InventoryPage(page);
    await inventory.expectLoaded();
    await page.waitForLoadState("networkidle");

    // Asserting the actual bug — every product's <img src> is identical —
    // is more robust than a pixel-diff baseline that depends on OS rendering.
    const srcs = await page
      .locator(".inventory_item_img img")
      .evaluateAll((imgs) => imgs.map((img) => (img as HTMLImageElement).src));

    expect(srcs.length).toBe(6);
    expect(new Set(srcs).size).toBe(1);

    // Save a full-page screenshot as evidence (release-gate criterion 5
    // checks for *.png under test-results/).
    await page.screenshot({
      path: path.join("test-results", "TS_06_problem_user-inventory.png"),
      fullPage: true,
    });
  });
});
