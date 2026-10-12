package learnerapp.oop;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.List;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

@Tag("exercise")
class CapturedPaymentTest {

  @Test
  void partialRefundsAddUp() {
    CapturedPayment payment = new CapturedPayment(5000);
    payment.refund(1200);
    payment.refund(800);
    assertEquals(2000, payment.refundedMinor());
    assertEquals(3000, payment.remainingMinor());
    assertEquals(List.of(1200L, 800L), payment.refunds());
  }

  @Test
  void aFullRefundIsAllowed() {
    CapturedPayment payment = new CapturedPayment(5000);
    payment.refund(5000);
    assertEquals(0, payment.remainingMinor());
  }

  @Test
  void refundingMoreThanRemainsIsRejectedAndChangesNothing() {
    CapturedPayment payment = new CapturedPayment(5000);
    payment.refund(4000);
    assertThrows(IllegalArgumentException.class, () -> payment.refund(1001));
    assertEquals(4000, payment.refundedMinor());
    assertEquals(List.of(4000L), payment.refunds());
  }

  @Test
  void zeroAndNegativeAmountsAreRejected() {
    CapturedPayment payment = new CapturedPayment(5000);
    assertThrows(IllegalArgumentException.class, () -> payment.refund(0));
    assertThrows(IllegalArgumentException.class, () -> payment.refund(-500));
    assertThrows(IllegalArgumentException.class, () -> new CapturedPayment(0));
    assertThrows(IllegalArgumentException.class, () -> new CapturedPayment(-1));
    assertEquals(5000, payment.remainingMinor());
  }

  @Test
  void callersCannotChangeTheRefunds() {
    CapturedPayment payment = new CapturedPayment(5000);
    payment.refund(1000);
    assertThrows(UnsupportedOperationException.class, () -> payment.refunds().add(9000L));
    assertThrows(UnsupportedOperationException.class, () -> payment.refunds().clear());
    assertEquals(4000, payment.remainingMinor());
  }

  @Test
  void hasNoPublicFields() {
    assertEquals(0, CapturedPayment.class.getFields().length, "state must be reachable only through methods");
  }
}
