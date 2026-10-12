package learnerapp.framework;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import learnerapp.framework.pages.CatalogPage;
import learnerapp.framework.pages.CheckoutPage;
import learnerapp.framework.pages.OrderPage;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.openqa.selenium.WebDriver;

/** End-to-end journeys through the shop, written only with the framework's page objects. */
@ExtendWith(ShopExtension.class)
class CheckoutJourneyTest {

  private static CheckoutPage checkoutWithEspresso(WebDriver driver, Shop shop) {
    return CatalogPage.open(driver, shop).addToCart("espresso-beans").header().goToCheckout();
  }

  @Test
  void aSuccessfulPaymentCreatesAPaidOrder(WebDriver driver, Shop shop) {
    CheckoutPage checkout = checkoutWithEspresso(driver, shop);
    assertEquals(1899, checkout.totalMinor());

    OrderPage order =
        checkout.enterEmail("learner@example.com").enterCard("sandpay-success", "Asha Rao").payAndExpectOrder();

    assertEquals("SUCCEEDED", order.status());
    assertEquals(1899, order.totalMinor());
    assertTrue(order.orderId().startsWith("ord_"), order.orderId());
  }

  @Test
  void aSlowPaymentStillEndsPaid(WebDriver driver, Shop shop) {
    OrderPage order =
        checkoutWithEspresso(driver, shop)
            .enterEmail("learner@example.com")
            .enterCard("sandpay-slow", "Asha Rao")
            .payAndExpectOrder();
    assertEquals("SUCCEEDED", order.status());
  }

  @Test
  void aDeclinedCardShowsTheReasonAndCanBeRetried(WebDriver driver, Shop shop) {
    CheckoutPage checkout =
        checkoutWithEspresso(driver, shop)
            .enterEmail("learner@example.com")
            .enterCard("sandpay-insufficient-funds", "Asha Rao");

    String message = checkout.payAndExpectDecline();

    assertTrue(message.contains("insufficient funds"), message);
    assertTrue(checkout.canPay(), "the shopper can try another card");
  }

  @Test
  void payStaysDisabledUntilTheDetailsAreComplete(WebDriver driver, Shop shop) {
    CheckoutPage checkout = checkoutWithEspresso(driver, shop);
    assertFalse(checkout.canPay());
    checkout.enterEmail("learner@example.com");
    assertFalse(checkout.canPay(), "no card yet");
    checkout.enterCard("sandpay-nope", "Asha Rao");
    assertTrue(checkout.cardFrame().error().startsWith("Unknown test card"));
    assertFalse(checkout.canPay(), "unknown test card");
  }
}
