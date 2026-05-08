import { Page, expect, Locator } from "@playwright/test";

export class CheckoutPage {
  readonly page: Page;
  readonly firstName: Locator;
  readonly lastName: Locator;
  readonly postalCode: Locator;
  readonly continueButton: Locator;
  readonly finishButton: Locator;
  readonly summaryItems: Locator;
  readonly subtotalLabel: Locator;
  readonly totalLabel: Locator;
  readonly successHeader: Locator;
  readonly errorMessage: Locator;

  constructor(page: Page) {
    this.page = page;
    this.firstName = page.locator("[data-test='firstName']");
    this.lastName = page.locator("[data-test='lastName']");
    this.postalCode = page.locator("[data-test='postalCode']");
    this.continueButton = page.locator("[data-test='continue']");
    this.finishButton = page.locator("[data-test='finish']");
    this.summaryItems = page.locator(".cart_item");
    this.subtotalLabel = page.locator(".summary_subtotal_label");
    this.totalLabel = page.locator(".summary_total_label");
    this.successHeader = page.locator(".complete-header");
    this.errorMessage = page.locator("[data-test='error']");
  }

  async fillCustomerInfo(first: string, last: string, postal: string) {
    await this.firstName.fill(first);
    await this.lastName.fill(last);
    await this.postalCode.fill(postal);
    await this.continueButton.click();
  }

  async expectStepOne() {
    await expect(this.page).toHaveURL(/\/checkout-step-one\.html/);
  }

  async expectStepTwo() {
    await expect(this.page).toHaveURL(/\/checkout-step-two\.html/);
  }

  async expectComplete() {
    await expect(this.page).toHaveURL(/\/checkout-complete\.html/);
    await expect(this.successHeader).toHaveText("Thank you for your order!");
  }

  async finish() {
    await this.finishButton.click();
  }

  async itemSubtotal(): Promise<number> {
    const text = await this.subtotalLabel.innerText();
    // "Item total: $29.99" → 29.99
    const match = text.match(/\$([0-9.]+)/);
    if (!match) throw new Error(`subtotal not parseable: ${text}`);
    return parseFloat(match[1]);
  }
}
