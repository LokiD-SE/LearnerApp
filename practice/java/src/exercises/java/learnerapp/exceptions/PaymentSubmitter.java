package learnerapp.exceptions;

/**
 * Exercise - handling a failure without hiding it.
 *
 * <p>Lesson: "Exceptions and resource management". Tests: {@code PaymentSubmitterTest}. Run: {@code mvn
 * test -Dtest=PaymentSubmitterTest}
 *
 * <p>{@link #submit} is supposed to turn a network failure into a {@link PaymentFailedException} that
 * says which payment failed and keeps the original exception as its cause. Programming errors (any
 * {@code RuntimeException} from the gateway) must not be disguised as payment failures - let them
 * through unchanged. Today the method does neither. Fix it, and fix {@link PaymentFailedException}.
 */
public final class PaymentSubmitter {

  private PaymentSubmitter() {}

  /** Sends the payment and returns the provider's response. */
  public static String submit(Gateway gateway, String paymentId) throws PaymentFailedException {
    try {
      return gateway.send(paymentId);
    } catch (Exception e) {
      e.printStackTrace();
      return null;
    }
  }
}
