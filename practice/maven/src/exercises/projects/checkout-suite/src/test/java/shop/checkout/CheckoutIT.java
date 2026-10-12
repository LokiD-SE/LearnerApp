package shop.checkout;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;

import org.junit.jupiter.api.Test;

/**
 * An integration test (the IT suffix is the convention). In a real project it would talk to a running
 * service. Run with -Dcheckout.it.fail=true to see what a failing integration test does to the build.
 */
class CheckoutIT {

  @Test
  void checkoutWorksEndToEnd() {
    assertNotEquals("true", System.getProperty("checkout.it.fail"), "failing on purpose: -Dcheckout.it.fail=true");
    assertEquals(2024, Checkout.totalWithFee(1999, 25));
  }
}
