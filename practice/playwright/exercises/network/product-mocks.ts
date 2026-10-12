// Exercise - controlling the network with page.route.
//
// Lesson: "Network mocking and API testing with Playwright". Tests: tests/product-mocks.spec.ts
// Run: npx playwright test tests/product-mocks.spec.ts
//
// The catalog loads its products from products.json. Make that one request return what a test needs -
// without touching any other request (the page, its script and styles must still load).
import type { Page } from '@playwright/test';
import type { Product } from '../../framework/product';

/** From now on, the catalog's products.json request returns exactly these products. */
export async function mockProducts(page: Page, products: Product[]): Promise<void> {
  // TODO
}

/** From now on, the catalog's products.json request fails with this HTTP status. */
export async function failProducts(page: Page, status: number): Promise<void> {
  // TODO
}
