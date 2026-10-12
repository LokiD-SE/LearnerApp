import { expect, test, type Page } from '@playwright/test';
import { CatalogPage } from '../framework/pages/catalog-page';
import type { CheckoutPage } from '../framework/pages/checkout-page';
import { finalStatus, processingFinished } from '../exercises/waits/order-status';

async function readyToPay(page: Page, testCard: string): Promise<CheckoutPage> {
  const catalog = await CatalogPage.open(page);
  await catalog.addToCart('oat-milk');
  const checkout = await catalog.header.goToCheckout();
  await checkout.enterEmail('learner@example.com');
  await checkout.enterCard(testCard, 'Asha Rao');
  return checkout;
}

async function millisToRun(action: () => Promise<unknown>): Promise<number> {
  const start = Date.now();
  await action();
  return Date.now() - start;
}

test.describe('waiting for order status', { tag: '@exercise' }, () => {
  test('follows a pending payment until it succeeds', async ({ page }) => {
    const order = await (await readyToPay(page, 'sandpay-unknown')).payAndExpectOrder();
    expect(await order.status()).toBe('PENDING');
    expect(await finalStatus(page)).toBe('SUCCEEDED');
  });

  test('returns a failure too', async ({ page }) => {
    await (await readyToPay(page, 'sandpay-pending-then-failed')).payAndExpectOrder();
    expect(await finalStatus(page)).toBe('FAILED');
  });

  test('gives up when the timeout runs out', async ({ page }) => {
    await (await readyToPay(page, 'sandpay-unknown')).payAndExpectOrder();
    let rejected = false;
    const took = await millisToRun(() => finalStatus(page, 800).catch(() => (rejected = true)));
    expect(rejected, 'a status that stays PENDING past the timeout must reject').toBe(true);
    expect(took).toBeLessThan(2_500);
  });

  test('returns at once when the status is already final', async ({ page }) => {
    await (await readyToPay(page, 'sandpay-success')).payAndExpectOrder();
    const took = await millisToRun(async () => expect(await finalStatus(page)).toBe('SUCCEEDED'));
    expect(took, 'no sleeping when there is nothing to wait for').toBeLessThan(1_500);
  });

  test('waits for the processing overlay to go', async ({ page }) => {
    const checkout = await readyToPay(page, 'sandpay-insufficient-funds');
    await checkout.pay();
    await expect(page.getByTestId('processing-overlay')).toBeVisible();
    await processingFinished(page);
    await expect(page.getByTestId('processing-overlay')).toBeHidden({ timeout: 1 });
    expect(await checkout.canPay()).toBe(true);
  });

  test('does not wait when there is no overlay', async ({ page }) => {
    await readyToPay(page, 'sandpay-success');
    expect(await millisToRun(() => processingFinished(page))).toBeLessThan(1_500);
  });
});
