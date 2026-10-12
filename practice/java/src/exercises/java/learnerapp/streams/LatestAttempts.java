package learnerapp.streams;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Exercise - collecting into a map when keys repeat.
 *
 * <p>Lesson: "Lambdas, functional interfaces and streams". Tests: {@code LatestAttemptsTest}. Run:
 * {@code mvn test -Dtest=LatestAttemptsTest}
 *
 * <p>Works with yesterday's test data - and throws with today's, which contains retried payments.
 * Fix it, keeping it a single stream pipeline.
 */
public final class LatestAttempts {

  private LatestAttempts() {}

  /**
   * Each payment id mapped to its latest attempt (the highest attempt number), ids in the order they
   * first appear in the list.
   */
  public static Map<String, Payment> byId(List<Payment> payments) {
    return payments.stream().collect(Collectors.toMap(Payment::id, payment -> payment));
  }
}
