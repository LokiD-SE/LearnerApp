package learnerapp.framework.pages;

import java.util.List;
import learnerapp.framework.Config;
import learnerapp.framework.Shop;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.Select;
import org.openqa.selenium.support.ui.WebDriverWait;

/** The product list. Products load asynchronously, and sorting re-renders the whole list. */
public final class CatalogPage {

  private static final By PRODUCT_LIST = By.cssSelector("[data-testid='product-list']");
  private static final By PRODUCT_NAMES = By.cssSelector("[data-testid='product-name']");
  private static final By SORT = By.cssSelector("[data-testid='sort']");

  private final WebDriver driver;
  private final WebDriverWait wait;

  private CatalogPage(WebDriver driver) {
    this.driver = driver;
    this.wait = new WebDriverWait(driver, Config.timeout());
  }

  public static CatalogPage open(WebDriver driver, Shop shop) {
    driver.get(shop.page("index.html"));
    return new CatalogPage(driver).waitUntilLoaded();
  }

  /** Adds one of a product, and returns when the cart badge shows it - not when the click happened. */
  public CatalogPage addToCart(String sku) {
    Header header = header();
    int before = header.cartCount();
    driver.findElement(By.cssSelector("[data-testid='add-to-cart-" + sku + "']")).click();
    wait.until(d -> header.cartCount() == before + 1);
    return this;
  }

  /** Sorts by the option's visible text, for example "Price: low to high". */
  public CatalogPage sortBy(String option) {
    new Select(driver.findElement(SORT)).selectByVisibleText(option);
    return waitUntilLoaded();
  }

  /** Product names in the order shown. */
  public List<String> productNames() {
    return driver.findElements(PRODUCT_NAMES).stream().map(WebElement::getText).toList();
  }

  public Header header() {
    return new Header(driver);
  }

  /** The list marks itself busy while it loads or re-sorts; it is ready when that ends. */
  private CatalogPage waitUntilLoaded() {
    wait.until(d -> "false".equals(d.findElement(PRODUCT_LIST).getDomAttribute("aria-busy")));
    return this;
  }
}
