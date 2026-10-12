// Reference solution - page.route intercepts requests whose URL matches the pattern, and
// route.fulfill answers them without reaching the server. The glob matches only products.json, so
// every other request goes to the network as usual.
import type { Page } from '@playwright/test';
import type { Product } from '../../framework/product';

export async function mockProducts(page: Page, products: Product[]): Promise<void> {
  await page.route('**/products.json', (route) => route.fulfill({ json: products }));
}

export async function failProducts(page: Page, status: number): Promise<void> {
  await page.route('**/products.json', (route) => route.fulfill({ status, body: 'Service unavailable' }));
}
