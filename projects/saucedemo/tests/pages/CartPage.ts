import { Page, expect, Locator } from "@playwright/test";

export class CartPage {
  readonly page: Page;
  readonly cartItems: Locator;
  readonly checkoutButton: Locator;
  readonly continueShoppingButton: Locator;

  constructor(page: Page) {
    this.page = page;
    this.cartItems = page.locator(".cart_item");
    this.checkoutButton = page.locator("[data-test='checkout']");
    this.continueShoppingButton = page.locator("[data-test='continue-shopping']");
  }

  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/cart\.html/);
  }

  async itemNames(): Promise<string[]> {
    return this.cartItems.locator(".inventory_item_name").allInnerTexts();
  }

  async removeItem(itemName: string) {
    const item = this.cartItems.filter({ hasText: itemName });
    await item.locator("button:has-text('Remove')").click();
  }

  async checkout() {
    await this.checkoutButton.click();
  }
}
