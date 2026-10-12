// Exercise - custom fixtures with test.extend.
//
// Lesson: "Fixtures and page objects in Playwright Test". Tests: tests/shop-fixtures.spec.ts
// Run: npx playwright test tests/shop-fixtures.spec.ts
//
// Tests that import `test` from this file can ask for `catalog` or `checkoutWithEspresso` as
// parameters, like the built-in `page`. Implement both fixtures. A fixture does its setup, hands its
// value to the test with `await use(value)`, and may clean up after `use` returns.
import { test as base } from '@playwright/test';
import type { CatalogPage } from '../../framework/pages/catalog-page';
import type { CheckoutPage } from '../../framework/pages/checkout-page';

export interface ShopFixtures {
  /** The product catalog, opened and fully loaded. */
  catalog: CatalogPage;
  /** The checkout page, with one espresso beans (sku espresso-beans) in the cart. */
  checkoutWithEspresso: CheckoutPage;
}

export const test = base.extend<ShopFixtures>({
  catalog: async ({ page }, use) => {
    throw new Error('TODO: open the catalog for this page, then await use(catalog)');
  },
  checkoutWithEspresso: async ({ page }, use) => {
    throw new Error('TODO: add espresso beans to the cart, go to the checkout, then await use(checkout)');
  },
});

export { expect } from '@playwright/test';
