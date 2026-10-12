// Reference solution - user-facing locators (label, role and accessible name) and test ids, combined
// with filter(): "the card that has a heading named exactly X, then its button". No XPath needed.
import type { Locator, Page } from '@playwright/test';

export function cartCount(page: Page): Locator {
  return page.getByTestId('cart-count');
}

export function sortSelect(page: Page): Locator {
  return page.getByLabel('Sort by');
}

export function productCards(page: Page): Locator {
  return page.getByTestId('product-card');
}

function card(page: Page, productName: string): Locator {
  return productCards(page).filter({ has: page.getByRole('heading', { name: productName, exact: true }) });
}

export function addToCartButton(page: Page, productName: string): Locator {
  return card(page, productName).getByRole('button', { name: 'Add to cart' });
}

export function priceOf(page: Page, productName: string): Locator {
  return card(page, productName).getByTestId('product-price');
}
