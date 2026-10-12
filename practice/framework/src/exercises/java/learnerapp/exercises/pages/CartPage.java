package learnerapp.exercises.pages;

import java.util.List;
import learnerapp.framework.Shop;
import learnerapp.framework.pages.CheckoutPage;
import org.openqa.selenium.WebDriver;

/**
 * Exercise - a page object for the cart page ({@code cart.html}).
 *
 * <p>Lesson: "Page objects done right". Tests: {@code CartPageTest}. Run: {@code mvn test
 * -Dtest=CartPageTest}
 *
 * <p>The framework has no cart page object yet, and new tests need one. Write it the way the existing
 * pages in {@code learnerapp.framework.pages} are written:
 *
 * <ul>
 *   <li>public methods speak the shopper's language and return data or the next page object - never a
 *       {@code WebElement} or a {@code By};
 *   <li>locators are private constants; each change waits until the page shows its result (the cart
 *       saves every change "on the server", which takes a moment);
 *   <li>no assertions inside - the tests decide what is right.
 * </ul>
 *
 * Useful hooks on the page: each line is {@code [data-testid='cart-line']} with a {@code data-sku}
 * attribute, and contains {@code line-name}, {@code line-quantity}, {@code increase}, {@code decrease}
 * and {@code remove} test ids. The total is {@code [data-testid='cart-total']}, with the amount in minor
 * units in {@code data-amount-minor}. An empty cart shows {@code [data-testid='cart-empty']}.
 */
public final class CartPage {

  private final WebDriver driver;

  public CartPage(WebDriver driver) {
    this.driver = driver;
  }

  public static CartPage open(WebDriver driver, Shop shop) {
    driver.get(shop.page("cart.html"));
    return new CartPage(driver);
  }

  /** The names of the products in the cart, in the order shown. */
  public List<String> productNames() {
    throw new UnsupportedOperationException("TODO");
  }

  /** The quantity of a product, by its visible name; 0 if it is not in the cart. */
  public int quantityOf(String productName) {
    throw new UnsupportedOperationException("TODO");
  }

  /** One more of a product, by its visible name. Returns when the page shows the new quantity. */
  public CartPage increaseQuantity(String productName) {
    throw new UnsupportedOperationException("TODO");
  }

  /** Removes a product, by its visible name. Returns when its line is gone. */
  public CartPage remove(String productName) {
    throw new UnsupportedOperationException("TODO");
  }

  /** The cart total in minor units (cents). */
  public long totalMinor() {
    throw new UnsupportedOperationException("TODO");
  }

  /** Whether the page shows the empty-cart message. */
  public boolean isEmpty() {
    throw new UnsupportedOperationException("TODO");
  }

  /** Follows the link to the checkout. */
  public CheckoutPage goToCheckout() {
    throw new UnsupportedOperationException("TODO");
  }
}
