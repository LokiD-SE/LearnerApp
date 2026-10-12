// Exercise - a page object for the cart page (cart.html), in TypeScript.
//
// Lesson: "Fixtures and page objects in Playwright Test". Tests: tests/cart-page.spec.ts
// Run: npx playwright test tests/cart-page.spec.ts
//
// Write it like the given page objects in framework/pages: methods named after what the shopper does,
// returning data or the next page object; locators kept inside; every change waits for the page to show
// its result (the cart "saves on the server" for a moment); no assertions about what is right - the tests
// decide that. Hooks on the page: each line is [data-testid=cart-line] with line-name, line-quantity,
// increase, decrease and remove test ids inside; the total is [data-testid=cart-total] with the amount
// in minor units in data-amount-minor; an empty cart shows [data-testid=cart-empty].
import type { Page } from '@playwright/test';
import type { CheckoutPage } from '../../framework/pages/checkout-page';

export class CartPage {
  constructor(private readonly page: Page) {}

  static async open(page: Page): Promise<CartPage> {
    await page.goto('cart.html');
    return new CartPage(page);
  }

  /** The names of the products in the cart, in the order shown. */
  async productNames(): Promise<string[]> {
    throw new Error('TODO');
  }

  /** The quantity of a product, by its visible name; 0 if it is not in the cart. */
  async quantityOf(productName: string): Promise<number> {
    throw new Error('TODO');
  }

  /** One more of a product. Resolves when the page shows the new quantity. */
  async increaseQuantity(productName: string): Promise<this> {
    throw new Error('TODO');
  }

  /** Removes a product. Resolves when its line is gone. */
  async remove(productName: string): Promise<this> {
    throw new Error('TODO');
  }

  /** The cart total in minor units (cents). */
  async totalMinor(): Promise<number> {
    throw new Error('TODO');
  }

  /** Whether the page shows the empty-cart message. */
  async isEmpty(): Promise<boolean> {
    throw new Error('TODO');
  }

  /** Follows the link to the checkout. */
  async goToCheckout(): Promise<CheckoutPage> {
    throw new Error('TODO');
  }
}
