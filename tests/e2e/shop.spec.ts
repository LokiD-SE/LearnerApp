import { expect, test, type Page } from '@playwright/test';

/** The practice shop is published with the app at ./shop/ - a smoke test of the deployed copy. */

async function buyEspresso(page: Page, testCard: string) {
  await page.goto('./shop/');
  const espresso = page.getByTestId('add-to-cart-espresso-beans');
  await espresso.click();
  await expect(page.getByTestId('cart-count')).toHaveText('1');
  await page.getByTestId('checkout-link').click();
  await expect(page.getByTestId('order-total')).toHaveText('€18.99');
  await page.getByTestId('email').fill('learner@example.com');
  const frame = page.frameLocator('[data-testid="sandpay-frame"]');
  await frame.getByTestId('card-input').fill(testCard);
  await frame.getByTestId('card-name').fill('Asha Rao');
  await page.getByTestId('pay-button').click();
}

test('a successful payment ends on a paid order, and the cart is emptied', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await buyEspresso(page, 'sandpay-success');
  await expect(page.getByTestId('processing-overlay')).toBeVisible();
  await expect(page.getByTestId('order-status')).toHaveText('SUCCEEDED', { timeout: 10_000 });
  await expect(page.getByTestId('cart-count')).toHaveText('0');
  expect(errors).toEqual([]);
});

test('a declined card shows the reason and lets the shopper retry', async ({ page }) => {
  await buyEspresso(page, 'sandpay-insufficient-funds');
  await expect(page.getByTestId('payment-error')).toHaveText(/insufficient funds/, { timeout: 10_000 });
  await expect(page.getByTestId('pay-button')).toBeEnabled();
});

test('an unknown outcome is pending first and settles on the order page', async ({ page }) => {
  await buyEspresso(page, 'sandpay-unknown');
  await expect(page.getByTestId('order-status')).toHaveText('PENDING', { timeout: 10_000 });
  await expect(page.getByTestId('order-status')).toHaveText('SUCCEEDED', { timeout: 10_000 });
});

test('lessons link to the published shop', async ({ page }) => {
  await page.goto('./#/lesson/selenium-waits-and-synchronisation');
  await page.getByText('Versions, sources and assumptions').click();
  await page.getByRole('link', { name: 'the published copy' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Coffee things' })).toBeVisible();
  await expect(page.getByTestId('product-card')).toHaveCount(6);
});
