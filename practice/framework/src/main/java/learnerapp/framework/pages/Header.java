package learnerapp.framework.pages;

import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;

/**
 * The header every shop page shares - a page <em>component</em>. Pages hand it out instead of each one
 * repeating its locators.
 */
public final class Header {

  private static final By CART_COUNT = By.cssSelector("[data-testid='cart-count']");
  private static final By CHECKOUT_LINK = By.cssSelector("[data-testid='checkout-link']");

  private final WebDriver driver;

  public Header(WebDriver driver) {
    this.driver = driver;
  }

  /** How many items the cart badge shows. */
  public int cartCount() {
    return Integer.parseInt(driver.findElement(CART_COUNT).getText().trim());
  }

  public CheckoutPage goToCheckout() {
    driver.findElement(CHECKOUT_LINK).click();
    return new CheckoutPage(driver);
  }
}
