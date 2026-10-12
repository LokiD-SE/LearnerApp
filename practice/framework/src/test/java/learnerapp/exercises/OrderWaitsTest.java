package learnerapp.exercises;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Duration;
import learnerapp.exercises.waits.OrderWaits;
import learnerapp.framework.Shop;
import learnerapp.framework.ShopExtension;
import learnerapp.framework.pages.CatalogPage;
import learnerapp.framework.pages.CheckoutPage;
import learnerapp.framework.pages.OrderPage;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.openqa.selenium.By;
import org.openqa.selenium.TimeoutException;
import org.openqa.selenium.WebDriver;

@Tag("exercise")
@ExtendWith(ShopExtension.class)
class OrderWaitsTest {

  private static final Duration GENEROUS = Duration.ofSeconds(10);

  private static CheckoutPage readyToPay(WebDriver driver, Shop shop, String testCard) {
    return CatalogPage.open(driver, shop)
        .addToCart("oat-milk")
        .header()
        .goToCheckout()
        .enterEmail("learner@example.com")
        .enterCard(testCard, "Asha Rao");
  }

  private static long millisToRun(Runnable action) {
    long start = System.nanoTime();
    action.run();
    return Duration.ofNanos(System.nanoTime() - start).toMillis();
  }

  @Test
  void waitsForAPendingPaymentToSucceed(WebDriver driver, Shop shop) {
    OrderPage order = readyToPay(driver, shop, "sandpay-unknown").payAndExpectOrder();
    assertEquals("PENDING", order.status(), "this test card starts PENDING");
    assertEquals("SUCCEEDED", OrderWaits.waitForFinalStatus(driver, GENEROUS));
  }

  @Test
  void returnsAFailureToo(WebDriver driver, Shop shop) {
    readyToPay(driver, shop, "sandpay-pending-then-failed").payAndExpectOrder();
    assertEquals("FAILED", OrderWaits.waitForFinalStatus(driver, GENEROUS));
  }

  @Test
  void givesUpWhenTheTimeoutRunsOut(WebDriver driver, Shop shop) {
    readyToPay(driver, shop, "sandpay-unknown").payAndExpectOrder();
    long took =
        millisToRun(
            () ->
                assertThrows(
                    TimeoutException.class,
                    () -> OrderWaits.waitForFinalStatus(driver, Duration.ofMillis(800))));
    assertTrue(took < 2500, "the wait must end when its timeout does, took " + took + " ms");
  }

  @Test
  void returnsAtOnceWhenTheStatusIsAlreadyFinal(WebDriver driver, Shop shop) {
    readyToPay(driver, shop, "sandpay-success").payAndExpectOrder();
    long took = millisToRun(() -> assertEquals("SUCCEEDED", OrderWaits.waitForFinalStatus(driver, GENEROUS)));
    assertTrue(took < 1500, "no sleeping when there is nothing to wait for, took " + took + " ms");
  }

  @Test
  void waitsForTheOverlayBeforeThePageCanBeUsed(WebDriver driver, Shop shop) {
    CheckoutPage checkout = readyToPay(driver, shop, "sandpay-insufficient-funds").pay();
    By overlay = By.cssSelector("[data-testid='processing-overlay']");
    assertTrue(driver.findElement(overlay).isDisplayed(), "the overlay covers the page while paying");

    OrderWaits.waitForProcessingToFinish(driver, GENEROUS);

    assertFalse(driver.findElement(overlay).isDisplayed());
    assertTrue(checkout.canPay(), "the page can be used again");
  }

  @Test
  void doesNotWaitWhenThereIsNoOverlay(WebDriver driver, Shop shop) {
    readyToPay(driver, shop, "sandpay-success");
    long took = millisToRun(() -> OrderWaits.waitForProcessingToFinish(driver, GENEROUS));
    assertTrue(took < 1500, "the overlay was never shown, took " + took + " ms");
  }
}
