import { test, expect } from "@playwright/test";
import { LoginPage } from "../pages/LoginPage";
import { InventoryPage } from "../pages/InventoryPage";

test.describe("TS_02 — Inventory + sort", () => {
  test.beforeEach(async ({ page }) => {
    const login = new LoginPage(page);
    await login.goto();
    await login.loginAs("standard");
  });

  test("TS_02_01 @smoke six items render on inventory", async ({ page }) => {
    const inventory = new InventoryPage(page);
    await inventory.expectLoaded();
    await expect(inventory.inventoryItems).toHaveCount(6);
  });

  test("TS_02_02 @regression sort A→Z is default and preserved", async ({
    page,
  }) => {
    const inventory = new InventoryPage(page);
    const names = await inventory.itemNames();
    const sorted = [...names].sort((a, b) => a.localeCompare(b));
    expect(names).toEqual(sorted);
  });

  test("TS_02_03 @regression sort price low→high orders prices ascending", async ({
    page,
  }) => {
    const inventory = new InventoryPage(page);
    await inventory.sortBy("lohi");
    const prices = await inventory.itemPrices();
    const sorted = [...prices].sort((a, b) => a - b);
    expect(prices).toEqual(sorted);
  });

  test("TS_02_04 @regression sort price high→low orders prices descending", async ({
    page,
  }) => {
    const inventory = new InventoryPage(page);
    await inventory.sortBy("hilo");
    const prices = await inventory.itemPrices();
    const sorted = [...prices].sort((a, b) => b - a);
    expect(prices).toEqual(sorted);
  });
});
