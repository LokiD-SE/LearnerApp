package learnerapp.exceptions;

/**
 * Exercise (with {@code PaymentSubmitter}) - a payment could not be submitted. Callers are expected to
 * handle it - check the outcome, retry with the same idempotency key, or report it - so it is a checked
 * exception.
 *
 * <p>It needs to carry the original exception as its cause. Add what is missing.
 */
public class PaymentFailedException extends Exception {

  public PaymentFailedException(String message) {
    super(message);
  }
}
