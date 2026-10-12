// Exercise - locators that survive reloads and re-sorting.
//
// Lesson: "Playwright locators, auto-waiting and web-first assertions". Tests: tests/shop-locators.spec.ts
// Run: npx playwright test tests/shop-locators.spec.ts
//
// Return one Locator per function. Prefer what the user sees (roles, labels, names) and the shop's
// data-testid hooks; never the generated ids (btn-..., product-...) or the generated card-... class,
// and never positions. Explore the page first: npx playwright codegen http://127.0.0.1:4310/
// (with the shop running: node scripts/serve-shop.mjs).
import type { Locator, Page } from '@playwright/test';

/** The cart count badge in the header. */
export function cartCount(page: Page): Locator {
  throw new Error('TODO: locate the cart count');
}

/** The "Sort by" drop-down. */
export function sortSelect(page: Page): Locator {
  throw new Error('TODO: locate the sort drop-down');
}

/** Every product card. */
export function productCards(page: Page): Locator {
  throw new Error('TODO: locate the product cards');
}

/** The "Add to cart" button of the product with exactly this visible name, wherever it is in the list. */
export function addToCartButton(page: Page, productName: string): Locator {
  throw new Error('TODO: locate the Add to cart button of a product by its name');
}

/** The price of the product with exactly this visible name. */
export function priceOf(page: Page, productName: string): Locator {
  throw new Error('TODO: locate the price of a product by its name');
}
