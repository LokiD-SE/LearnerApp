package learnerapp.framework.pages;

import learnerapp.framework.Config;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

/**
 * The order confirmation. Some payments are PENDING when this page opens; the page then checks again
 * every second and updates the status by itself.
 */
public final class OrderPage {

  private static final By ORDER_ID = By.cssSelector("[data-testid='order-id']");
  private static final By STATUS = By.cssSelector("[data-testid='order-status']");
  private static final By TOTAL = By.cssSelector("[data-testid='order-total']");

  private final WebDriver driver;

  /** Waits until the browser is on the order page and the status is shown. */
  public OrderPage(WebDriver driver) {
    this.driver = driver;
    WebDriverWait wait = new WebDriverWait(driver, Config.timeout());
    wait.until(ExpectedConditions.urlContains("order.html"));
    wait.until(d -> !d.findElement(STATUS).getText().isBlank());
  }

  public String orderId() {
    return driver.findElement(ORDER_ID).getText();
  }

  /** The status shown right now: PENDING, SUCCEEDED or FAILED. */
  public String status() {
    return driver.findElement(STATUS).getText().trim();
  }

  public long totalMinor() {
    return Long.parseLong(driver.findElement(TOTAL).getDomAttribute("data-amount-minor"));
  }
}
