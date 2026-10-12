import { expect, type Locator, type Page } from '@playwright/test';

/** The order confirmation. Some payments are PENDING when it opens; the page updates the status itself. */
export class OrderPage {
  private readonly statusLabel: Locator;

  private constructor(private readonly page: Page) {
    this.statusLabel = page.getByTestId('order-status');
  }

  /** Waits until the browser is on the order page and a status is shown. */
  static async loaded(page: Page): Promise<OrderPage> {
    await expect(page).toHaveURL(/order\.html/);
    const order = new OrderPage(page);
    await expect(order.statusLabel).not.toBeEmpty();
    return order;
  }

  async orderId(): Promise<string> {
    return (await this.page.getByTestId('order-id').textContent())?.trim() ?? '';
  }

  /** The status shown right now: PENDING, SUCCEEDED or FAILED. */
  async status(): Promise<string> {
    return (await this.statusLabel.textContent())?.trim() ?? '';
  }

  async totalMinor(): Promise<number> {
    return Number(await this.page.getByTestId('order-total').getAttribute('data-amount-minor'));
  }
}
