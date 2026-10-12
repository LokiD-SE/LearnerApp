import { expect, type Locator, type Page } from '@playwright/test';
import { OrderPage } from './order-page';
import { SandPayCardFrame } from './sandpay-card-frame';

/** Checkout: summary, email, the SandPay card frame and the Pay button. Paying shows an overlay until the outcome is known. */
export class CheckoutPage {
  readonly card: SandPayCardFrame;
  private readonly payButton: Locator;

  private constructor(private readonly page: Page) {
    this.card = new SandPayCardFrame(page.frameLocator('[data-testid="sandpay-frame"]'));
    this.payButton = page.getByTestId('pay-button');
  }

  static async open(page: Page): Promise<CheckoutPage> {
    await page.goto('checkout.html');
    return CheckoutPage.loaded(page);
  }

  /** For navigation that has already happened: waits for the checkout page. */
  static async loaded(page: Page): Promise<CheckoutPage> {
    await expect(page).toHaveURL(/checkout\.html/);
    return new CheckoutPage(page);
  }

  /** The order total in minor units, from the page's data attribute. */
  async totalMinor(): Promise<number> {
    return Number(await this.page.getByTestId('order-total').getAttribute('data-amount-minor'));
  }

  async enterEmail(email: string): Promise<this> {
    await this.page.getByLabel('Email for the receipt').fill(email);
    return this;
  }

  async enterCard(testCard: string, nameOnCard: string): Promise<this> {
    await this.card.enter(testCard, nameOnCard);
    return this;
  }

  async canPay(): Promise<boolean> {
    return this.payButton.isEnabled();
  }

  /** Clicks Pay (Playwright waits until it is enabled) and returns at once, while the payment is processing. */
  async pay(): Promise<this> {
    await this.payButton.click();
    return this;
  }

  /** Pays and waits for the order page - for test cards that create an order. */
  async payAndExpectOrder(): Promise<OrderPage> {
    await this.pay();
    return OrderPage.loaded(this.page);
  }

  /** Pays and waits for the decline message - for test cards that are declined. */
  async payAndExpectDecline(): Promise<string> {
    await this.pay();
    await expect(this.page.getByTestId('processing-overlay')).toBeHidden();
    const error = this.page.getByTestId('payment-error');
    await expect(error).not.toBeEmpty();
    return (await error.textContent())?.trim() ?? '';
  }
}
