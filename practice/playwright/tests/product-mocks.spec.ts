import { expect, test } from '@playwright/test';
import type { Product } from '../framework/product';
import { failProducts, mockProducts } from '../exercises/network/product-mocks';

const twoProducts: Product[] = [
  { sku: 'test-kettle', name: 'Test kettle', price: 4500, featured: 1 },
  { sku: 'test-scale', name: 'Test scale', price: 2999, featured: 2 },
];

test.describe('mocking the catalog API', { tag: '@exercise' }, () => {
  test('the catalog shows exactly the mocked products', async ({ page }) => {
    await mockProducts(page, twoProducts);
    await page.goto('index.html');
    await expect(page.getByTestId('product-name')).toHaveText(['Test kettle', 'Test scale']);
    await expect(page.getByTestId('product-price').first()).toHaveText('€45.00');
  });

  test('an empty catalog has no cards and no error', async ({ page }) => {
    await mockProducts(page, []);
    await page.goto('index.html');
    await expect(page.getByTestId('product-list')).toHaveAttribute('aria-busy', 'false');
    await expect(page.getByTestId('product-card')).toHaveCount(0);
    await expect(page.getByTestId('catalog-error')).toHaveCount(0);
  });

  test('a failing API shows the error state with a way to retry', async ({ page }) => {
    await failProducts(page, 503);
    await page.goto('index.html');
    await expect(page.getByTestId('catalog-error')).toContainText('Products could not be loaded.');
    await expect(page.getByTestId('retry')).toBeVisible();
  });

  test('only products.json is affected', async ({ page }) => {
    await failProducts(page, 500);
    await page.goto('index.html');
    await expect(page.getByRole('heading', { level: 1, name: 'Coffee things' })).toBeVisible();
    await expect(page.getByTestId('cart-count'), 'the page script still loaded and ran').toHaveText('0');
  });
});
