package learnerapp.exercises.waits;

import java.time.Duration;
import org.openqa.selenium.WebDriver;

/**
 * Exercise - waiting for things that happen later, without sleeping.
 *
 * <p>Lesson: "Explicit waits and synchronisation". Tests: {@code OrderWaitsTest}. Run: {@code mvn test
 * -Dtest=OrderWaitsTest}
 *
 * <p>Use {@code WebDriverWait}. No {@code Thread.sleep} and no implicit wait: the tests check that you
 * return as soon as the condition is true, and give up when the timeout runs out.
 */
public final class OrderWaits {

  private OrderWaits() {}

  /**
   * On the order page: waits until the status ({@code [data-testid='order-status']}) is final -
   * SUCCEEDED or FAILED - and returns it. Some payments show PENDING first; the page updates the status
   * by itself a few seconds later.
   *
   * @throws org.openqa.selenium.TimeoutException if no final status appears within {@code timeout}
   */
  public static String waitForFinalStatus(WebDriver driver, Duration timeout) {
    throw new UnsupportedOperationException("TODO: wait for a final order status");
  }

  /**
   * On the checkout page: waits until the processing overlay ({@code [data-testid='processing-overlay']})
   * is gone, so the page can be used again. Returns at once if the overlay is not shown.
   *
   * @throws org.openqa.selenium.TimeoutException if the overlay is still shown after {@code timeout}
   */
  public static void waitForProcessingToFinish(WebDriver driver, Duration timeout) {
    throw new UnsupportedOperationException("TODO: wait for the overlay to disappear");
  }
}
