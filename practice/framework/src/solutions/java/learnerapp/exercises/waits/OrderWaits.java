package learnerapp.exercises.waits;

import java.time.Duration;
import java.util.Set;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

/**
 * Reference solution - explicit waits on the condition the test cares about.
 *
 * <p>{@code WebDriverWait.until} calls the condition straight away, then every 500 ms by default, until
 * it returns something other than null or false (which {@code until} returns) or the timeout ends with
 * a {@code TimeoutException}.
 */
public final class OrderWaits {

  private static final By STATUS = By.cssSelector("[data-testid='order-status']");
  private static final By OVERLAY = By.cssSelector("[data-testid='processing-overlay']");
  private static final Set<String> FINAL = Set.of("SUCCEEDED", "FAILED");

  private OrderWaits() {}

  public static String waitForFinalStatus(WebDriver driver, Duration timeout) {
    return new WebDriverWait(driver, timeout)
        .withMessage("a final order status (SUCCEEDED or FAILED)")
        .until(
            d -> {
              String status = d.findElement(STATUS).getText().trim();
              return FINAL.contains(status) ? status : null; // null means "not yet, ask again"
            });
  }

  public static void waitForProcessingToFinish(WebDriver driver, Duration timeout) {
    // true at once when the overlay is hidden (or not on the page at all)
    new WebDriverWait(driver, timeout).until(ExpectedConditions.invisibilityOfElementLocated(OVERLAY));
  }
}
