import { expect, test } from '@playwright/test';
import { fetchProducts } from '../exercises/api/products-api';

test.describe('the catalog API', { tag: '@exercise' }, () => {
  test('returns the six products', async ({ request }) => {
    const products = await fetchProducts(request);
    expect(products.map((p) => p.sku)).toEqual([
      'espresso-beans',
      'oat-milk',
      'pour-over-kit',
      'ceramic-mug',
      'hand-grinder',
      'filter-papers',
    ]);
  });

  test('prices are positive whole numbers of minor units', async ({ request }) => {
    for (const product of await fetchProducts(request)) {
      expect(Number.isInteger(product.price) && product.price > 0, product.sku).toBe(true);
    }
  });

  test('a missing endpoint is reported with its status', async ({ playwright, baseURL }) => {
    const elsewhere = await playwright.request.newContext({ baseURL: `${baseURL}nowhere/` });
    await expect(fetchProducts(elsewhere)).rejects.toThrow(/404/);
    await elsewhere.dispose();
  });

  test('a malformed response is rejected', async ({ playwright, baseURL }) => {
    test.skip(Boolean(process.env.SHOP_URL), 'the broken endpoint exists only on the local test server');
    const broken = await playwright.request.newContext({ baseURL: `${baseURL}broken/` });
    await expect(fetchProducts(broken)).rejects.toThrow(/not a valid product/);
    await broken.dispose();
  });
});
