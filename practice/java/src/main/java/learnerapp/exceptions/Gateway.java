package learnerapp.exceptions;

import java.io.IOException;

/** The network connection to SandPay: sends a payment and returns the provider's response. */
@FunctionalInterface
public interface Gateway {

  /**
   * @throws IOException when the network fails - the payment's outcome is then unknown
   */
  String send(String paymentId) throws IOException;
}
