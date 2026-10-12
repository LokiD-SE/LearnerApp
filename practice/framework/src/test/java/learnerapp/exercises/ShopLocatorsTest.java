package learnerapp.exercises;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

import java.util.List;
import java.util.regex.Pattern;
import learnerapp.exercises.locators.ShopLocators;
import learnerapp.framework.Config;
import learnerapp.framework.Shop;
import learnerapp.framework.ShopExtension;
import learnerapp.framework.pages.CatalogPage;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.WebDriverWait;

@Tag("exercise")
@ExtendWith(ShopExtension.class)
class ShopLocatorsTest {

  /** Generated per page load in the shop: ids such as btn-k2j4l1 and classes such as card-x8f2k. */
  private static final Pattern GENERATED = Pattern.compile("(btn|product)-[a-z0-9]{6}\\b|card-[a-z0-9]{5}\\b");

  private static WebElement only(WebDriver driver, By locator) {
    List<WebElement> found = driver.findElements(locator);
    assertEquals(1, found.size(), locator + " must find exactly one element, found " + found.size());
    return found.get(0);
  }

  private static WebElement byTestId(WebDriver driver, String testId) {
    return driver.findElement(By.cssSelector("[data-testid='" + testId + "']"));
  }

  private static WebElement cardOf(WebDriver driver, String sku) {
    return driver.findElement(By.cssSelector("[data-testid='product-card'][data-sku='" + sku + "']"));
  }

  private static void assertStable(By locator) {
    String text = locator.toString();
    assertFalse(GENERATED.matcher(text).find(), locator + " uses an id or class that changes on every load");
    assertFalse(text.contains("/html"), locator + " is an absolute path from the document root");
  }

  @Test
  void findsTheCartCountAndTheSortDropDown(WebDriver driver, Shop shop) {
    CatalogPage.open(driver, shop);
    assertEquals(byTestId(driver, "cart-count"), only(driver, ShopLocators.cartCount()));
    assertEquals(byTestId(driver, "sort"), only(driver, ShopLocators.sortSelect()));
    assertStable(ShopLocators.cartCount());
    assertStable(ShopLocators.sortSelect());
  }

  @Test
  void findsEveryProductCard(WebDriver driver, Shop shop) {
    CatalogPage.open(driver, shop);
    assertEquals(6, driver.findElements(ShopLocators.productCards()).size());
    assertStable(ShopLocators.productCards());
  }

  @Test
  void findsAProductsButtonAndPriceByItsName(WebDriver driver, Shop shop) {
    CatalogPage.open(driver, shop);
    WebElement oatMilk = cardOf(driver, "oat-milk");
    assertEquals(oatMilk.findElement(By.tagName("button")), only(driver, ShopLocators.addToCartButton("Oat milk 1 L")));
    assertEquals("€2.49", only(driver, ShopLocators.priceOf("Oat milk 1 L")).getText());
    assertEquals("€59.90", only(driver, ShopLocators.priceOf("Hand grinder")).getText());
    assertStable(ShopLocators.addToCartButton("Oat milk 1 L"));
    assertStable(ShopLocators.priceOf("Oat milk 1 L"));
  }

  @Test
  void keepsWorkingAfterTheListIsReordered(WebDriver driver, Shop shop) {
    CatalogPage catalog = CatalogPage.open(driver, shop);
    catalog.sortBy("Price: high to low");
    WebElement grinder = cardOf(driver, "hand-grinder");
    assertEquals(grinder.findElement(By.tagName("button")), only(driver, ShopLocators.addToCartButton("Hand grinder")));

    catalog.sortBy("Price: low to high");
    only(driver, ShopLocators.addToCartButton("Ceramic mug")).click();
    new WebDriverWait(driver, Config.timeout())
        .until(d -> "1".equals(byTestId(d, "cart-count").getText()));

    CatalogPage.open(driver, shop); // a new load: new ids and classes
    assertEquals("1", only(driver, ShopLocators.cartCount()).getText());
    assertEquals(
        cardOf(driver, "ceramic-mug").findElement(By.tagName("button")),
        only(driver, ShopLocators.addToCartButton("Ceramic mug")));
  }

  @Test
  void needsTheExactName(WebDriver driver, Shop shop) {
    CatalogPage.open(driver, shop);
    assertEquals(0, driver.findElements(ShopLocators.addToCartButton("Oat milk")).size(),
        "\"Oat milk\" is not a product - only \"Oat milk 1 L\" is");
  }
}
