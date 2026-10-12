package learnerapp.basics;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

@Tag("exercise")
class PaymentChecksTest {

  /** A status read from a response body, the way real code gets it - not a literal in the source. */
  private static String statusFrom(String body) {
    return body.substring(body.indexOf('=') + 1);
  }

  @Test
  void literalStatusSucceeds() {
    assertTrue(PaymentChecks.isSucceeded("SUCCEEDED"));
  }

  @Test
  void statusParsedFromAResponseSucceeds() {
    assertTrue(PaymentChecks.isSucceeded(statusFrom("status=SUCCEEDED")));
    assertTrue(PaymentChecks.isSucceeded(new StringBuilder("SUCCEEDED").toString()));
  }

  @Test
  void otherStatusesAndNoStatusDoNotSucceed() {
    assertFalse(PaymentChecks.isSucceeded(statusFrom("status=FAILED")));
    assertFalse(PaymentChecks.isSucceeded("succeeded"));
    assertFalse(PaymentChecks.isSucceeded(null));
  }

  @Test
  void smallEqualCountsMatch() {
    assertTrue(PaymentChecks.sameAttemptCount(3, 3));
  }

  @Test
  void largeEqualCountsMatch() {
    // Integer.valueOf only guarantees the same object for -128 to 127
    assertTrue(PaymentChecks.sameAttemptCount(Integer.valueOf(1000), Integer.valueOf(1000)));
    assertTrue(PaymentChecks.sameAttemptCount(Integer.parseInt("250"), Integer.parseInt("250")));
  }

  @Test
  void differentOrUnknownCountsDoNotMatch() {
    assertFalse(PaymentChecks.sameAttemptCount(3, 4));
    assertFalse(PaymentChecks.sameAttemptCount(null, 3));
    assertFalse(PaymentChecks.sameAttemptCount(3, null));
    assertFalse(PaymentChecks.sameAttemptCount(null, null));
  }
}
