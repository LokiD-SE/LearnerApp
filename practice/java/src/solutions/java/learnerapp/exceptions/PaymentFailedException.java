package learnerapp.exceptions;

/**
 * Reference solution - a checked exception with a (message, cause) constructor, so the original
 * failure travels with it and appears as "Caused by:" in the stack trace.
 */
public class PaymentFailedException extends Exception {

  public PaymentFailedException(String message) {
    super(message);
  }

  public PaymentFailedException(String message, Throwable cause) {
    super(message, cause);
  }
}
