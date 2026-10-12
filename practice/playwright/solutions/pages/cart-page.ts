// Reference solution - lines found by product name with filter(), every change confirmed with a
// web-first assertion, and only data or page objects returned.
import { expect, type Locator, type Page } from '@playwright/test';
import { CheckoutPage } from '../../framework/pages/checkout-page';

const exactly = (text: string) => new RegExp(`^${text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`);

export class CartPage {
  private readonly lines: Locator;

  constructor(private readonly page: Page) {
    this.lines = page.getByTestId('cart-line');
  }

  static async open(page: Page): Promise<CartPage> {
    await page.goto('cart.html');
    return new CartPage(page);
  }

  async productNames(): Promise<string[]> {
    return this.lines.getByTestId('line-name').allTextContents();
  }

  async quantityOf(productName: string): Promise<number> {
    const line = this.line(productName);
    if ((await line.count()) === 0) return 0;
    return Number(await line.getByTestId('line-quantity').textContent());
  }

  async increaseQuantity(productName: string): Promise<this> {
    const before = await this.quantityOf(productName);
    await this.line(productName).getByTestId('increase').click();
    await expect(this.line(productName).getByTestId('line-quantity')).toHaveText(String(before + 1));
    return this;
  }

  async remove(productName: string): Promise<this> {
    await this.line(productName).getByTestId('remove').click();
    await expect(this.line(productName)).toHaveCount(0);
    return this;
  }

  async totalMinor(): Promise<number> {
    return Number(await this.page.getByTestId('cart-total').getAttribute('data-amount-minor'));
  }

  async isEmpty(): Promise<boolean> {
    return this.page.getByTestId('cart-empty').isVisible();
  }

  async goToCheckout(): Promise<CheckoutPage> {
    await this.page.getByTestId('go-to-checkout').click();
    return CheckoutPage.loaded(this.page);
  }

  private line(productName: string): Locator {
    return this.lines.filter({
      has: this.page.getByTestId('line-name').filter({ hasText: exactly(productName) }),
    });
  }
}
