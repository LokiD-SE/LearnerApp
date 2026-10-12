package learnerapp.framework.pages;

import java.util.function.Supplier;
import learnerapp.framework.Config;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

/**
 * The SandPay card fields, which live in an iframe - a component with its own document. Every method
 * switches into the frame and always switches back, so callers never have to think about frames.
 */
public final class SandPayCardFrame {

  private static final By CARD = By.cssSelector("[data-testid='card-input']");
  private static final By NAME = By.cssSelector("[data-testid='card-name']");
  private static final By ERROR = By.cssSelector("[data-testid='card-error']");

  private final WebDriver driver;
  private final By frame;
  private final WebDriverWait wait;

  SandPayCardFrame(WebDriver driver, By frame) {
    this.driver = driver;
    this.frame = frame;
    this.wait = new WebDriverWait(driver, Config.timeout());
  }

  /** Types a test card code (such as {@code sandpay-success}) and the name on the card. */
  public void enter(String testCard, String nameOnCard) {
    inFrame(
        () -> {
          type(CARD, testCard);
          type(NAME, nameOnCard);
          return null;
        });
  }

  /** The validation message under the card field, or an empty string. */
  public String error() {
    return inFrame(() -> driver.findElement(ERROR).getText());
  }

  private void type(By field, String text) {
    WebElement input = driver.findElement(field);
    input.clear();
    input.sendKeys(text);
  }

  private <T> T inFrame(Supplier<T> action) {
    wait.until(ExpectedConditions.frameToBeAvailableAndSwitchToIt(frame));
    try {
      return action.get();
    } finally {
      driver.switchTo().defaultContent();
    }
  }
}
