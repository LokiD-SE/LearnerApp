// Reference solution - request.get uses the configured baseURL, response.ok() checks the 2xx range,
// and the body is validated before anyone relies on it, so a broken API fails with a clear message
// instead of an undefined somewhere later.
import type { APIRequestContext } from '@playwright/test';
import type { Product } from '../../framework/product';

function isProduct(value: unknown): value is Product {
  const p = value as Partial<Product> | null;
  return (
    typeof p === 'object' &&
    p !== null &&
    typeof p.sku === 'string' &&
    typeof p.name === 'string' &&
    Number.isInteger(p.price) &&
    (p.price ?? 0) > 0
  );
}

export async function fetchProducts(request: APIRequestContext): Promise<Product[]> {
  const response = await request.get('products.json');
  if (!response.ok()) {
    throw new Error(`GET products.json failed with HTTP ${response.status()}`);
  }
  const body: unknown = await response.json();
  if (!Array.isArray(body)) throw new Error('products.json is not a list');
  const bad = body.findIndex((item) => !isProduct(item));
  if (bad >= 0)
    throw new Error(`products.json item ${bad} is not a valid product: ${JSON.stringify(body[bad])}`);
  return body as Product[];
}
