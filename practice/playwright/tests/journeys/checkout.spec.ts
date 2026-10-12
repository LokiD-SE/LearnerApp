import { expect, test } from '@playwright/test';
import { CatalogPage } from '../../framework/pages/catalog-page';
import type { CheckoutPage } from '../../framework/pages/checkout-page';

/** End-to-end journeys written only with the given page objects - not an exercise. */

async function checkoutWithEspresso(page: import('@playwright/test').Page): Promise<CheckoutPage> {
  const catalog = await CatalogPage.open(page);
  await catalog.addToCart('espresso-beans');
  return catalog.header.goToCheckout();
}

test('a successful payment creates a paid order', async ({ page }) => {
  const checkout = await checkoutWithEspresso(page);
  expect(await checkout.totalMinor()).toBe(1899);
  await checkout.enterEmail('learner@example.com');
  await checkout.enterCard('sandpay-success', 'Asha Rao');
  const order = await checkout.payAndExpectOrder();
  expect(await order.status()).toBe('SUCCEEDED');
  expect(await order.orderId()).toMatch(/^ord_/);
});

test('a declined card shows the reason and can be retried', async ({ page }) => {
  const checkout = await checkoutWithEspresso(page);
  await checkout.enterEmail('learner@example.com');
  await checkout.enterCard('sandpay-insufficient-funds', 'Asha Rao');
  expect(await checkout.payAndExpectDecline()).toContain('insufficient funds');
  expect(await checkout.canPay()).toBe(true);
});

test('an unknown test card is rejected inside the SandPay frame', async ({ page }) => {
  const checkout = await checkoutWithEspresso(page);
  await checkout.enterEmail('learner@example.com');
  await checkout.enterCard('sandpay-nope', 'Asha Rao');
  expect(await checkout.card.error()).toMatch(/^Unknown test card/);
  expect(await checkout.canPay()).toBe(false);
});
