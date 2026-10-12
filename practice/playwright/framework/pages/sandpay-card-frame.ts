import type { FrameLocator } from '@playwright/test';

/**
 * The SandPay card fields, inside an iframe. A FrameLocator scopes every lookup to the frame - no
 * switching in and out, unlike Selenium.
 */
export class SandPayCardFrame {
  constructor(private readonly frame: FrameLocator) {}

  async enter(testCard: string, nameOnCard: string): Promise<void> {
    await this.frame.getByLabel('Test card').fill(testCard);
    await this.frame.getByLabel('Name on card').fill(nameOnCard);
  }

  async error(): Promise<string> {
    return (await this.frame.getByTestId('card-error').textContent())?.trim() ?? '';
  }
}
