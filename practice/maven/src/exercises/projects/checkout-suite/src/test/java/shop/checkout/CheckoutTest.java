package shop.checkout;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;

/** Fast unit tests - these run on every build. */
class CheckoutTest {

  @Test
  void addsTheFee() {
    assertEquals(2024, Checkout.totalWithFee(1999, 25));
  }

  @Test
  void rejectsNegativeAmounts() {
    assertThrows(IllegalArgumentException.class, () -> Checkout.totalWithFee(-1, 25));
  }
}
