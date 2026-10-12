package learnerapp.framework.pages;

import learnerapp.framework.Config;
import learnerapp.framework.Shop;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

/**
 * Checkout: summary, email, the SandPay card frame and the Pay button. Paying shows an overlay over the
 * whole page until the outcome is known; the methods below wait for the outcome they expect.
 */
public final class CheckoutPage {

  private static final By TOTAL = By.cssSelector("[data-testid='order-total']");
  private static final By EMAIL = By.cssSelector("[data-testid='email']");
  private static final By CARD_FRAME = By.cssSelector("[data-testid='sandpay-frame']");
  private static final By PAY = By.cssSelector("[data-testid='pay-button']");
  private static final By ERROR = By.cssSelector("[data-testid='payment-error']");
  private static final By OVERLAY = By.cssSelector("[data-testid='processing-overlay']");

  private final WebDriver driver;
  private final WebDriverWait wait;

  public CheckoutPage(WebDriver driver) {
    this.driver = driver;
    this.wait = new WebDriverWait(driver, Config.timeout());
    wait.until(ExpectedConditions.urlContains("checkout.html"));
  }

  public static CheckoutPage open(WebDriver driver, Shop shop) {
    driver.get(shop.page("checkout.html"));
    return new CheckoutPage(driver);
  }

  /** The order total in minor units (cents), read from the page's data attribute. */
  public long totalMinor() {
    return Long.parseLong(driver.findElement(TOTAL).getDomAttribute("data-amount-minor"));
  }

  public CheckoutPage enterEmail(String email) {
    WebElement field = driver.findElement(EMAIL);
    field.clear();
    field.sendKeys(email);
    return this;
  }

  public CheckoutPage enterCard(String testCard, String nameOnCard) {
    cardFrame().enter(testCard, nameOnCard);
    return this;
  }

  public SandPayCardFrame cardFrame() {
    return new SandPayCardFrame(driver, CARD_FRAME);
  }

  /** Whether the Pay button can be used - it stays disabled until the details are complete. */
  public boolean canPay() {
    return driver.findElement(PAY).isEnabled();
  }

  /** Clicks Pay and returns at once, while the payment is still processing. */
  public CheckoutPage pay() {
    wait.until(ExpectedConditions.elementToBeClickable(PAY)).click();
    return this;
  }

  /** Pays and waits for the order page - for test cards that create an order. */
  public OrderPage payAndExpectOrder() {
    pay();
    return new OrderPage(driver);
  }

  /** Pays and waits for the decline message - for test cards that are declined. */
  public String payAndExpectDecline() {
    pay();
    wait.until(ExpectedConditions.invisibilityOfElementLocated(OVERLAY));
    return wait.until(d -> {
      String message = d.findElement(ERROR).getText().trim();
      return message.isEmpty() ? null : message;
    });
  }
}
