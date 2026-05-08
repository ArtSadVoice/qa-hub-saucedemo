import { test, expect } from "@playwright/test";
import { LoginPage } from "../pages/LoginPage";
import { InventoryPage } from "../pages/InventoryPage";

test.describe("TS_05 — Logout", () => {
  test("TS_05_01 @smoke logout returns to login screen", async ({ page }) => {
    const login = new LoginPage(page);
    await login.goto();
    await login.loginAs("standard");

    const inventory = new InventoryPage(page);
    await inventory.expectLoaded();
    await inventory.logout();

    // Back on login form
    await expect(login.username).toBeVisible();
    await expect(page).toHaveURL(/saucedemo\.com\/?$/);
  });
});
