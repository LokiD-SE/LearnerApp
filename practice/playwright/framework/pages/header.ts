import { expect, type Locator, type Page } from '@playwright/test';
import { CheckoutPage } from './checkout-page';

/** The header every shop page shares - a component that pages hand out. */
export class Header {
  /** The cart badge. Public so page objects can wait on it; tests read cartCount() instead. */
  readonly count: Locator;

  constructor(private readonly page: Page) {
    this.count = page.getByTestId('cart-count');
  }

  async cartCount(): Promise<number> {
    return Number((await this.count.textContent())?.trim());
  }

  async expectCartCount(count: number): Promise<void> {
    await expect(this.count).toHaveText(String(count));
  }

  async goToCheckout(): Promise<CheckoutPage> {
    await this.page.getByTestId('checkout-link').click();
    return CheckoutPage.loaded(this.page);
  }
}
