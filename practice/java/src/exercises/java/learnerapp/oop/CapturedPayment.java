package learnerapp.oop;

import java.util.ArrayList;
import java.util.List;

/**
 * Exercise - an object that protects its own rules.
 *
 * <p>Lesson: "Encapsulation, inheritance, polymorphism and abstraction". Tests: {@code
 * CapturedPaymentTest}. Run: {@code mvn test -Dtest=CapturedPaymentTest}
 *
 * <p>A captured payment can be refunded in parts, but never by more than was captured. Today any code
 * can break that rule - through the public fields, through the list that {@link #refunds()} hands out,
 * or simply by calling {@link #refund} with a bad amount. Make the class keep its rules itself. Keep the
 * constructor and the public methods; the fields may change.
 *
 * <p>Rules: the captured amount is positive; every refund is positive; the refunds never add up to more
 * than the captured amount. A refund that would break a rule throws {@code IllegalArgumentException}
 * and changes nothing.
 */
public class CapturedPayment {

  public long capturedMinor;
  public List<Long> refunds = new ArrayList<>();

  public CapturedPayment(long capturedMinor) {
    this.capturedMinor = capturedMinor;
  }

  public void refund(long amountMinor) {
    refunds.add(amountMinor);
  }

  public long refundedMinor() {
    long total = 0;
    for (long refund : refunds) total += refund;
    return total;
  }

  public long remainingMinor() {
    return capturedMinor - refundedMinor();
  }

  /** The refunds so far, oldest first. Callers can read them, not change them. */
  public List<Long> refunds() {
    return refunds;
  }
}
