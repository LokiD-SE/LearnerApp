package learnerapp.exercises.locators;

import org.openqa.selenium.By;

/**
 * Reference solution - locators built on attributes that exist for tests ({@code data-testid}) and on
 * what the user sees (the product name), never on generated ids, hashed classes or positions.
 */
public final class ShopLocators {

  private ShopLocators() {}

  public static By cartCount() {
    return By.cssSelector("[data-testid='cart-count']");
  }

  public static By sortSelect() {
    return By.cssSelector("[data-testid='sort']");
  }

  public static By productCards() {
    return By.cssSelector("[data-testid='product-card']");
  }

  public static By addToCartButton(String productName) {
    // CSS cannot match text, so XPath: the card whose name is exactly this text, then its button
    return By.xpath(card(productName) + "//button");
  }

  public static By priceOf(String productName) {
    return By.xpath(card(productName) + "//*[@data-testid='product-price']");
  }

  private static String card(String productName) {
    // product names here contain no quotes; a general helper would have to escape them
    return "//*[@data-testid='product-card'][.//*[@data-testid='product-name'][normalize-space()='"
        + productName
        + "']]";
  }
}
