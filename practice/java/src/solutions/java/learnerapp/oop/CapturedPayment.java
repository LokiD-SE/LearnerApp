package learnerapp.oop;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Reference solution - private state, validated in the constructor and in every method that changes
 * it, and a read-only view for callers. No code outside this class can make the payment invalid.
 */
public class CapturedPayment {

  private final long capturedMinor;
  private final List<Long> refunds = new ArrayList<>();
  private long refundedMinor;

  public CapturedPayment(long capturedMinor) {
    if (capturedMinor <= 0) {
      throw new IllegalArgumentException("Captured amount must be positive: " + capturedMinor);
    }
    this.capturedMinor = capturedMinor;
  }

  public void refund(long amountMinor) {
    if (amountMinor <= 0) {
      throw new IllegalArgumentException("Refund must be positive: " + amountMinor);
    }
    if (amountMinor > remainingMinor()) {
      throw new IllegalArgumentException(
          "Refund of " + amountMinor + " exceeds the remaining " + remainingMinor());
    }
    // validate first, change state last - a rejected refund changes nothing
    refunds.add(amountMinor);
    refundedMinor += amountMinor;
  }

  public long refundedMinor() {
    return refundedMinor;
  }

  public long remainingMinor() {
    return capturedMinor - refundedMinor;
  }

  public List<Long> refunds() {
    return Collections.unmodifiableList(refunds);
  }
}
