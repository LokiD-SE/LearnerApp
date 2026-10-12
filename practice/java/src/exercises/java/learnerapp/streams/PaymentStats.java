package learnerapp.streams;

import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Exercise - questions about a list of payments, answered with streams.
 *
 * <p>Lesson: "Lambdas, functional interfaces and streams". Tests: {@code PaymentStatsTest}. Run: {@code
 * mvn test -Dtest=PaymentStatsTest}
 *
 * <p>Write each method as one stream pipeline - no loops, and no changing variables outside the stream.
 */
public final class PaymentStats {

  private PaymentStats() {}

  /** The sum of the amounts of SUCCEEDED payments in this currency (0 if there are none). */
  public static long succeededTotal(List<Payment> payments, String currency) {
    throw new UnsupportedOperationException("TODO");
  }

  /** How many payments have each status, for example {SUCCEEDED=3, FAILED=1}. */
  public static Map<String, Long> countByStatus(List<Payment> payments) {
    throw new UnsupportedOperationException("TODO");
  }

  /** The FAILED payment with the largest amount, or empty if no payment failed. */
  public static Optional<Payment> largestFailed(List<Payment> payments) {
    throw new UnsupportedOperationException("TODO");
  }

  /**
   * The payment ids for each method, methods in alphabetical order, ids in the order of the list:
   * {bank-transfer=[pay_3], card=[pay_1, pay_4]}.
   */
  public static Map<String, List<String>> idsByMethod(List<Payment> payments) {
    throw new UnsupportedOperationException("TODO");
  }
}
