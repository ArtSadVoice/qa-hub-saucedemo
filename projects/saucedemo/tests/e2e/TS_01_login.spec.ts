import { test, expect } from "@playwright/test";
import { LoginPage } from "../pages/LoginPage";
import { InventoryPage } from "../pages/InventoryPage";

test.describe("TS_01 — Login", () => {
  test("TS_01_01 @smoke standard_user lands on inventory", async ({ page }) => {
    const login = new LoginPage(page);
    await login.goto();
    await login.loginAs("standard");

    const inventory = new InventoryPage(page);
    await inventory.expectLoaded();
  });

  test("TS_01_02 @regression locked_out_user shows error", async ({ page }) => {
    const login = new LoginPage(page);
    await login.goto();
    await login.loginAs("locked");
    await login.expectLockedOutError();
    // URL should NOT have advanced
    await expect(page).toHaveURL(/saucedemo\.com\/?$/);
  });

  test("TS_01_03 @regression empty credentials surface error", async ({ page }) => {
    const login = new LoginPage(page);
    await login.goto();
    await login.loginButton.click();
    await expect(login.errorMessage).toContainText("Username is required");
  });

  test("TS_01_04 @regression wrong password shows generic error", async ({ page }) => {
    const login = new LoginPage(page);
    await login.goto();
    await login.username.fill("standard_user");
    await login.password.fill("wrong_password");
    await login.loginButton.click();
    await expect(login.errorMessage).toContainText(
      "Username and password do not match"
    );
  });
});
