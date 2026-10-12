// Reference solution - fixtures build on each other: checkoutWithEspresso asks for catalog, which asks
// for the built-in page. Each test gets its own page, in its own browser context, so fixtures never leak
// state (cookies, storage, the cart) into other tests.
import { test as base } from '@playwright/test';
import { CatalogPage } from '../../framework/pages/catalog-page';
import type { CheckoutPage } from '../../framework/pages/checkout-page';

export interface ShopFixtures {
  catalog: CatalogPage;
  checkoutWithEspresso: CheckoutPage;
}

export const test = base.extend<ShopFixtures>({
  catalog: async ({ page }, use) => {
    await use(await CatalogPage.open(page));
  },
  checkoutWithEspresso: async ({ catalog }, use) => {
    await catalog.addToCart('espresso-beans');
    await use(await catalog.header.goToCheckout());
  },
});

export { expect } from '@playwright/test';
