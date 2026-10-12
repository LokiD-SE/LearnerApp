package learnerapp.exceptions;

import java.io.IOException;

/**
 * Reference solution - catch only what this method can handle (the network failure), translate it into
 * the caller's vocabulary with context, and keep the cause. Everything else propagates untouched.
 */
public final class PaymentSubmitter {

  private PaymentSubmitter() {}

  public static String submit(Gateway gateway, String paymentId) throws PaymentFailedException {
    try {
      return gateway.send(paymentId);
    } catch (IOException e) {
      throw new PaymentFailedException(
          "Could not submit payment " + paymentId + " - outcome unknown, check it before retrying", e);
    }
  }
}
