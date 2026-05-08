import { Page, expect, Locator } from "@playwright/test";

/**
 * https://www.saucedemo.com/ — the login screen.
 *
 * Useful test users (per saucedemo's footer):
 *   standard_user             — happy path
 *   locked_out_user           — blocked at login (should see error)
 *   problem_user              — broken images on inventory
 *   performance_glitch_user   — slow login + slow nav
 *   error_user                — random failures
 *   visual_user               — visual regressions
 */
export const TEST_USERS = {
  standard: "standard_user",
  locked: "locked_out_user",
  problem: "problem_user",
  performance: "performance_glitch_user",
  error: "error_user",
  visual: "visual_user",
} as const;

export const PASSWORD = "secret_sauce";

export class LoginPage {
  readonly page: Page;
  readonly username: Locator;
  readonly password: Locator;
  readonly loginButton: Locator;
  readonly errorMessage: Locator;

  constructor(page: Page) {
    this.page = page;
    this.username = page.locator("[data-test='username']");
    this.password = page.locator("[data-test='password']");
    this.loginButton = page.locator("[data-test='login-button']");
    this.errorMessage = page.locator("[data-test='error']");
  }

  async goto() {
    await this.page.goto("/");
    await expect(this.username).toBeVisible();
  }

  async loginAs(user: keyof typeof TEST_USERS) {
    await this.username.fill(TEST_USERS[user]);
    await this.password.fill(PASSWORD);
    await this.loginButton.click();
  }

  async expectLockedOutError() {
    await expect(this.errorMessage).toContainText(
      "Sorry, this user has been locked out"
    );
  }
}
