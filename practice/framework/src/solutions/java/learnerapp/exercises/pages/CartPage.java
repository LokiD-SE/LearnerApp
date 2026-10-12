package learnerapp.exercises.pages;

import java.util.List;
import java.util.Optional;
import learnerapp.framework.Config;
import learnerapp.framework.Shop;
import learnerapp.framework.pages.CheckoutPage;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.WebDriverWait;

/**
 * Reference solution - the cart page as the shopper sees it. Lines are found by product name, every
 * change waits for its visible result, and only data and page objects leave this class.
 */
public final class CartPage {

  private static final By LINES = By.cssSelector("[data-testid='cart-line']");
  private static final By LINE_NAME = By.cssSelector("[data-testid='line-name']");
  private static final By LINE_QUANTITY = By.cssSelector("[data-testid='line-quantity']");
  private static final By INCREASE = By.cssSelector("[data-testid='increase']");
  private static final By REMOVE = By.cssSelector("[data-testid='remove']");
  private static final By TOTAL = By.cssSelector("[data-testid='cart-total']");
  private static final By EMPTY = By.cssSelector("[data-testid='cart-empty']");
  private static final By CHECKOUT = By.cssSelector("[data-testid='go-to-checkout']");

  private final WebDriver driver;
  private final WebDriverWait wait;

  public CartPage(WebDriver driver) {
    this.driver = driver;
    this.wait = new WebDriverWait(driver, Config.timeout());
  }

  public static CartPage open(WebDriver driver, Shop shop) {
    driver.get(shop.page("cart.html"));
    return new CartPage(driver);
  }

  public List<String> productNames() {
    return driver.findElements(LINES).stream().map(line -> line.findElement(LINE_NAME).getText()).toList();
  }

  public int quantityOf(String productName) {
    return line(productName).map(line -> Integer.parseInt(line.findElement(LINE_QUANTITY).getText())).orElse(0);
  }

  public CartPage increaseQuantity(String productName) {
    int before = quantityOf(productName);
    requiredLine(productName).findElement(INCREASE).click();
    // the page re-renders the cart after saving; ask again until the new quantity shows
    wait.until(d -> quantityOf(productName) == before + 1);
    return this;
  }

  public CartPage remove(String productName) {
    requiredLine(productName).findElement(REMOVE).click();
    wait.until(d -> line(productName).isEmpty());
    return this;
  }

  public long totalMinor() {
    return Long.parseLong(driver.findElement(TOTAL).getDomAttribute("data-amount-minor"));
  }

  public boolean isEmpty() {
    return driver.findElement(EMPTY).isDisplayed();
  }

  public CheckoutPage goToCheckout() {
    driver.findElement(CHECKOUT).click();
    return new CheckoutPage(driver);
  }

  private Optional<WebElement> line(String productName) {
    return driver.findElements(LINES).stream()
        .filter(line -> line.findElement(LINE_NAME).getText().equals(productName))
        .findFirst();
  }

  private WebElement requiredLine(String productName) {
    return line(productName)
        .orElseThrow(() -> new IllegalArgumentException("No cart line for " + productName + ": " + productNames()));
  }
}
