import { Page, expect, Locator } from "@playwright/test";

export type SortOption =
  | "az"  // Name (A to Z) — default
  | "za"  // Name (Z to A)
  | "lohi" // Price (low to high)
  | "hilo"; // Price (high to low)

export class InventoryPage {
  readonly page: Page;
  readonly title: Locator;
  readonly inventoryItems: Locator;
  readonly sortDropdown: Locator;
  readonly cartLink: Locator;
  readonly cartBadge: Locator;
  readonly burgerMenu: Locator;
  readonly logoutLink: Locator;

  constructor(page: Page) {
    this.page = page;
    this.title = page.locator(".title");
    this.inventoryItems = page.locator(".inventory_item");
    this.sortDropdown = page.locator("[data-test='product-sort-container']");
    this.cartLink = page.locator(".shopping_cart_link");
    this.cartBadge = page.locator(".shopping_cart_badge");
    this.burgerMenu = page.locator("#react-burger-menu-btn");
    this.logoutLink = page.locator("#logout_sidebar_link");
  }

  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/inventory\.html/);
    await expect(this.title).toHaveText("Products");
    await expect(this.inventoryItems).not.toHaveCount(0);
  }

  async itemNames(): Promise<string[]> {
    return this.inventoryItems.locator(".inventory_item_name").allInnerTexts();
  }

  async itemPrices(): Promise<number[]> {
    const texts = await this.inventoryItems
      .locator(".inventory_item_price")
      .allInnerTexts();
    return texts.map((t) => parseFloat(t.replace("$", "")));
  }

  async sortBy(option: SortOption) {
    await this.sortDropdown.selectOption(option);
  }

  async addToCart(itemName: string) {
    const item = this.inventoryItems.filter({ hasText: itemName });
    await item.locator("button:has-text('Add to cart')").click();
  }

  async removeFromCart(itemName: string) {
    const item = this.inventoryItems.filter({ hasText: itemName });
    await item.locator("button:has-text('Remove')").click();
  }

  async expectCartCount(n: number) {
    if (n === 0) {
      await expect(this.cartBadge).toHaveCount(0);
    } else {
      await expect(this.cartBadge).toHaveText(String(n));
    }
  }

  async openCart() {
    await this.cartLink.click();
  }

  async logout() {
    await this.burgerMenu.click();
    await this.logoutLink.click();
  }
}
