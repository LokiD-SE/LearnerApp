package learnerapp.basics;

/**
 * Exercise - two checks that pass a quick unit test and fail with real data.
 *
 * <p>Lesson: "Primitive and reference types". Tests: {@code PaymentChecksTest}. Run: {@code mvn test
 * -Dtest=PaymentChecksTest}
 *
 * <p>Both methods compile and look right. Find out why the tests fail, then fix the methods without
 * changing their signatures.
 */
public final class PaymentChecks {

  private PaymentChecks() {}

  /**
   * True if the status the provider reported is exactly {@code SUCCEEDED}. A null status means the
   * provider has not reported one yet, which is not a success.
   */
  public static boolean isSucceeded(String status) {
    return status == "SUCCEEDED";
  }

  /**
   * True if the client and the server counted the same number of attempts. A null count is unknown,
   * and an unknown count never matches anything - not even another unknown.
   */
  public static boolean sameAttemptCount(Integer clientCount, Integer serverCount) {
    return clientCount == serverCount;
  }
}
