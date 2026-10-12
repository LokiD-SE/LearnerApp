package learnerapp.exceptions;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.net.SocketTimeoutException;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

@Tag("exercise")
class PaymentSubmitterTest {

  @Test
  void returnsTheResponseWhenAllGoesWell() throws Exception {
    assertEquals("SUCCEEDED", PaymentSubmitter.submit(id -> "SUCCEEDED", "pay_81Fz"));
  }

  @Test
  void aNetworkFailureBecomesAPaymentFailureWithContextAndCause() {
    IOException timeout = new SocketTimeoutException("Read timed out");
    PaymentFailedException failure =
        assertThrows(
            PaymentFailedException.class,
            () ->
                PaymentSubmitter.submit(
                    id -> {
                      throw timeout;
                    },
                    "pay_81Fz"));
    assertTrue(failure.getMessage().contains("pay_81Fz"), "say which payment: " + failure.getMessage());
    assertSame(timeout, failure.getCause(), "keep the original exception as the cause");
  }

  @Test
  void programmingErrorsAreNotDisguisedAsPaymentFailures() {
    IllegalStateException bug = new IllegalStateException("gateway not configured");
    IllegalStateException thrown =
        assertThrows(
            IllegalStateException.class,
            () ->
                PaymentSubmitter.submit(
                    id -> {
                      throw bug;
                    },
                    "pay_81Fz"));
    assertSame(bug, thrown);
  }

  @Test
  void paymentFailedExceptionIsChecked() {
    assertTrue(Exception.class.isAssignableFrom(PaymentFailedException.class));
    assertFalse(RuntimeException.class.isAssignableFrom(PaymentFailedException.class));
  }
}
