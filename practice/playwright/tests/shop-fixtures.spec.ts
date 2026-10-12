import { expect, test } from '../exercises/fixtures/shop-test';

test.describe('shop fixtures', { tag: '@exercise' }, () => {
  test('catalog is the loaded product list', async ({ catalog, page }) => {
    await expect(page).toHaveURL(/index\.html/);
    expect(await catalog.productNames()).toHaveLength(6);
  });

  test('checkoutWithEspresso is a checkout with one espresso beans', async ({
    checkoutWithEspresso,
    page,
  }) => {
    await expect(page).toHaveURL(/checkout\.html/);
    expect(await checkoutWithEspresso.totalMinor()).toBe(1899);
  });

  test('every test gets a fresh cart', async ({ checkoutWithEspresso }) => {
    // the previous test also added espresso beans - in its own browser context
    expect(await checkoutWithEspresso.totalMinor()).toBe(1899);
  });
});
