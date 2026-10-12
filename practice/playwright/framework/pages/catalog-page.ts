import { expect, type Locator, type Page } from '@playwright/test';
import { Header } from './header';

/** The product list. Products load from products.json, and sorting re-renders the whole list. */
export class CatalogPage {
  readonly header: Header;
  private readonly list: Locator;

  constructor(private readonly page: Page) {
    this.header = new Header(page);
    this.list = page.getByTestId('product-list');
  }

  static async open(page: Page): Promise<CatalogPage> {
    await page.goto('index.html');
    const catalog = new CatalogPage(page);
    await catalog.waitUntilLoaded();
    return catalog;
  }

  /** Adds one of a product, and resolves when the cart badge shows it - not when the click happened. */
  async addToCart(sku: string): Promise<this> {
    const before = await this.header.cartCount();
    await this.page.getByTestId(`add-to-cart-${sku}`).click();
    await this.header.expectCartCount(before + 1);
    return this;
  }

  /** Sorts by the option's visible text, for example "Price: low to high". */
  async sortBy(option: string): Promise<this> {
    await this.page.getByLabel('Sort by').selectOption({ label: option });
    await this.waitUntilLoaded();
    return this;
  }

  async productNames(): Promise<string[]> {
    return this.page.getByTestId('product-name').allTextContents();
  }

  /** The list marks itself busy while it loads or re-sorts; it is ready when that ends. */
  private async waitUntilLoaded(): Promise<void> {
    await expect(this.list).toHaveAttribute('aria-busy', 'false');
  }
}
