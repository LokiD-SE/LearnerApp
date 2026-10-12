package learnerapp.basics;

/**
 * Reference solution - compare object values with {@code equals}, never with {@code ==}.
 *
 * <p>{@code ==} on two references asks "is this the same object?". String literals are interned and
 * small boxed integers (-128 to 127) are cached, so {@code ==} happens to work for them - which is why
 * the bug survives quick tests that use literals and small numbers.
 */
public final class PaymentChecks {

  private PaymentChecks() {}

  public static boolean isSucceeded(String status) {
    // the literal first: "SUCCEEDED".equals(null) is false, status.equals(...) would throw
    return "SUCCEEDED".equals(status);
  }

  public static boolean sameAttemptCount(Integer clientCount, Integer serverCount) {
    // Objects.equals(null, null) is true, which the rule above forbids
    return clientCount != null && clientCount.equals(serverCount);
  }
}
