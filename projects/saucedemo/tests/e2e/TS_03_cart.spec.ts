import { test, expect } from "@playwright/test";
import { LoginPage } from "../pages/LoginPage";
import { InventoryPage } from "../pages/InventoryPage";
import { CartPage } from "../pages/CartPage";

const BACKPACK = "Sauce Labs Backpack";
const BIKE_LIGHT = "Sauce Labs Bike Light";

test.describe("TS_03 — Cart", () => {
  test.beforeEach(async ({ page }) => {
    const login = new LoginPage(page);
    await login.goto();
    await login.loginAs("standard");
  });

  test("TS_03_01 @smoke add one item — cart badge shows 1", async ({ page }) => {
    const inventory = new InventoryPage(page);
    await inventory.expectLoaded();
    await inventory.addToCart(BACKPACK);
    await inventory.expectCartCount(1);
  });

  test("TS_03_02 @e2e add two items, open cart, both listed", async ({ page }) => {
    const inventory = new InventoryPage(page);
    await inventory.expectLoaded();
    await inventory.addToCart(BACKPACK);
    await inventory.addToCart(BIKE_LIGHT);
    await inventory.expectCartCount(2);

    await inventory.openCart();
    const cart = new CartPage(page);
    await cart.expectLoaded();
    const names = await cart.itemNames();
    expect(names).toEqual(expect.arrayContaining([BACKPACK, BIKE_LIGHT]));
  });

  test("TS_03_03 @regression remove item from inventory clears badge", async ({
    page,
  }) => {
    const inventory = new InventoryPage(page);
    await inventory.expectLoaded();
    await inventory.addToCart(BACKPACK);
    await inventory.expectCartCount(1);
    await inventory.removeFromCart(BACKPACK);
    await inventory.expectCartCount(0);
  });

  test("TS_03_04 @regression remove from cart page", async ({ page }) => {
    const inventory = new InventoryPage(page);
    await inventory.expectLoaded();
    await inventory.addToCart(BACKPACK);
    await inventory.openCart();

    const cart = new CartPage(page);
    await cart.expectLoaded();
    await cart.removeItem(BACKPACK);
    await expect(cart.cartItems).toHaveCount(0);
  });
});
