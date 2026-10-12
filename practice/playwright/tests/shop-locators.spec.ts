import { expect, test } from '@playwright/test';
import { CatalogPage } from '../framework/pages/catalog-page';
import {
  addToCartButton,
  cartCount,
  priceOf,
  productCards,
  sortSelect,
} from '../exercises/locators/shop-locators';

test.describe('shop locators', { tag: '@exercise' }, () => {
  test.beforeEach(async ({ page }) => {
    await CatalogPage.open(page);
  });

  test('find the cart count and the sort drop-down', async ({ page }) => {
    await expect(cartCount(page)).toHaveCount(1);
    await expect(cartCount(page)).toHaveAttribute('data-testid', 'cart-count');
    await expect(sortSelect(page)).toHaveCount(1);
    await expect(sortSelect(page)).toHaveAttribute('data-testid', 'sort');
  });

  test('find every product card', async ({ page }) => {
    await expect(productCards(page)).toHaveCount(6);
  });

  test("find a product's button and price by its name", async ({ page }) => {
    await expect(addToCartButton(page, 'Oat milk 1 L')).toHaveAttribute(
      'data-testid',
      'add-to-cart-oat-milk',
    );
    await expect(priceOf(page, 'Oat milk 1 L')).toHaveText('€2.49');
    await expect(priceOf(page, 'Hand grinder')).toHaveText('€59.90');
  });

  test('keep working after re-sorting and reloading', async ({ page }) => {
    const catalog = new CatalogPage(page);
    await catalog.sortBy('Price: high to low');
    await expect(addToCartButton(page, 'Hand grinder')).toHaveAttribute(
      'data-testid',
      'add-to-cart-hand-grinder',
    );

    await catalog.sortBy('Price: low to high');
    await addToCartButton(page, 'Ceramic mug').click(); // strict: fails if the locator matches more than one
    await expect(cartCount(page)).toHaveText('1');

    await CatalogPage.open(page); // a new load: new generated ids and classes
    await expect(addToCartButton(page, 'Ceramic mug')).toHaveAttribute(
      'data-testid',
      'add-to-cart-ceramic-mug',
    );
    await expect(cartCount(page)).toHaveText('1');
  });

  test('need the exact name', async ({ page }) => {
    await expect(
      addToCartButton(page, 'Oat milk'),
      '"Oat milk" is not a product - "Oat milk 1 L" is',
    ).toHaveCount(0);
  });
});
