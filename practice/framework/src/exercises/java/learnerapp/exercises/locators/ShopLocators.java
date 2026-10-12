package learnerapp.exercises.locators;

import org.openqa.selenium.By;

/**
 * Exercise - locators that survive UI changes.
 *
 * <p>Lesson: "Locator strategy - CSS, XPath and stable attributes". Tests: {@code ShopLocatorsTest}.
 * Run: {@code mvn test -Dtest=ShopLocatorsTest}
 *
 * <p>Open the shop's product page ({@code practice/shop/index.html}, or the published copy) with your
 * browser's developer tools and write one locator per method. Each must find exactly the right
 * element(s) on every page load, in any sort order. Watch out: the {@code id} of every button and card
 * and one CSS class of every card are generated anew on each load.
 */
public final class ShopLocators {

  private ShopLocators() {}

  /** The cart count badge in the header. */
  public static By cartCount() {
    throw new UnsupportedOperationException("TODO: locate the cart count");
  }

  /** The "Sort by" drop-down. */
  public static By sortSelect() {
    throw new UnsupportedOperationException("TODO: locate the sort drop-down");
  }

  /** Every product card - all of them. */
  public static By productCards() {
    throw new UnsupportedOperationException("TODO: locate the product cards");
  }

  /**
   * The "Add to cart" button of the product with this visible name, for example {@code "Oat milk 1 L"}
   * - wherever that product is in the list. Use the name, not the product's sku.
   */
  public static By addToCartButton(String productName) {
    throw new UnsupportedOperationException("TODO: locate a product's Add to cart button by its name");
  }

  /** The price of the product with this visible name. */
  public static By priceOf(String productName) {
    throw new UnsupportedOperationException("TODO: locate a product's price by its name");
  }
}
