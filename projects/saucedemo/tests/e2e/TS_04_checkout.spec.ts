import { test, expect } from "@playwright/test";
import { LoginPage } from "../pages/LoginPage";
import { InventoryPage } from "../pages/InventoryPage";
import { CartPage } from "../pages/CartPage";
import { CheckoutPage } from "../pages/CheckoutPage";

const BACKPACK = "Sauce Labs Backpack";

test.describe("TS_04 — Checkout flow", () => {
  test.beforeEach(async ({ page }) => {
    const login = new LoginPage(page);
    await login.goto();
    await login.loginAs("standard");
  });

  test("TS_04_01 @e2e full happy path — login → cart → checkout → success", async ({
    page,
  }) => {
    const inventory = new InventoryPage(page);
    await inventory.expectLoaded();
    await inventory.addToCart(BACKPACK);
    await inventory.openCart();

    const cart = new CartPage(page);
    await cart.expectLoaded();
    await cart.checkout();

    const checkout = new CheckoutPage(page);
    await checkout.expectStepOne();
    await checkout.fillCustomerInfo("Demo", "User", "10110");

    await checkout.expectStepTwo();
    await checkout.finish();

    await checkout.expectComplete();
  });

  test("TS_04_02 @regression checkout step-one validates required fields", async ({
    page,
  }) => {
    const inventory = new InventoryPage(page);
    await inventory.addToCart(BACKPACK);
    await inventory.openCart();
    await new CartPage(page).checkout();

    const checkout = new CheckoutPage(page);
    await checkout.expectStepOne();
    await checkout.continueButton.click();
    await expect(checkout.errorMessage).toContainText("First Name is required");
  });

  test("TS_04_03 @regression checkout step-two subtotal matches item price", async ({
    page,
  }) => {
    const inventory = new InventoryPage(page);
    await inventory.addToCart(BACKPACK);

    // The Backpack is $29.99 on the inventory page
    const inventoryPrices = await inventory.itemPrices();
    const expectedPrice = 29.99;
    expect(inventoryPrices).toContain(expectedPrice);

    await inventory.openCart();
    await new CartPage(page).checkout();
    const checkout = new CheckoutPage(page);
    await checkout.fillCustomerInfo("Demo", "User", "10110");
    await checkout.expectStepTwo();

    const subtotal = await checkout.itemSubtotal();
    expect(subtotal).toBeCloseTo(expectedPrice, 2);
  });
});
