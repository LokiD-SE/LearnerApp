// Exercise - API testing with Playwright's request context.
//
// Lesson: "Network mocking and API testing with Playwright". Tests: tests/products-api.spec.ts
// Run: npx playwright test tests/products-api.spec.ts
import type { APIRequestContext } from '@playwright/test';
import type { Product } from '../../framework/product';

/**
 * GETs products.json (relative to the request context's baseURL) and returns the products.
 *
 * - If the response is not OK, throws an Error whose message contains the HTTP status.
 * - If the body is not a list of products - each with a string sku, a string name and a price that is
 *   a positive whole number of minor units - throws an Error naming the first bad product.
 */
export async function fetchProducts(request: APIRequestContext): Promise<Product[]> {
  return [];
}
