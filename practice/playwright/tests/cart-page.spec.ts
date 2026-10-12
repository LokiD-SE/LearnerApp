import { expect, test, type Page } from '@playwright/test';
import { CatalogPage } from '../framework/pages/catalog-page';
import { CartPage } from '../exercises/pages/cart-page';

const ESPRESSO = 'Espresso beans 1 kg';
const OAT_MILK = 'Oat milk 1 L';

/** Two espresso beans (2 x 18.99) and one oat milk (2.49). */
async function cartWithThreeItems(page: Page): Promise<CartPage> {
  const catalog = await CatalogPage.open(page);
  await catalog.addToCart('espresso-beans');
  await catalog.addToCart('espresso-beans');
  await catalog.addToCart('oat-milk');
  return CartPage.open(page);
}

test.describe('CartPage', { tag: '@exercise' }, () => {
  test('shows what is in the cart', async ({ page }) => {
    const cart = await cartWithThreeItems(page);
    expect(await cart.productNames()).toEqual([ESPRESSO, OAT_MILK]);
    expect(await cart.quantityOf(ESPRESSO)).toBe(2);
    expect(await cart.quantityOf(OAT_MILK)).toBe(1);
    expect(await cart.quantityOf('Hand grinder')).toBe(0);
    expect(await cart.totalMinor()).toBe(2 * 1899 + 249);
    expect(await cart.isEmpty()).toBe(false);
  });

  test('an increase is visible as soon as the method resolves', async ({ page }) => {
    const cart = await cartWithThreeItems(page);
    await cart.increaseQuantity(OAT_MILK);
    expect(await cart.quantityOf(OAT_MILK), 'increaseQuantity must wait for the saved quantity').toBe(2);
    expect(await cart.totalMinor()).toBe(2 * 1899 + 2 * 249);
  });

  test('removing every line empties the cart', async ({ page }) => {
    const cart = await cartWithThreeItems(page);
    await cart.remove(ESPRESSO);
    expect(await cart.productNames(), 'remove must wait until the line is gone').toEqual([OAT_MILK]);
    await cart.remove(OAT_MILK);
    expect(await cart.isEmpty()).toBe(true);
  });

  test('leads to the checkout', async ({ page }) => {
    const checkout = await (await cartWithThreeItems(page)).goToCheckout();
    expect(await checkout.totalMinor()).toBe(2 * 1899 + 249);
  });
});
