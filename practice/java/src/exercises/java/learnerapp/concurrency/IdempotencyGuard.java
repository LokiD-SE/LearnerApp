package learnerapp.concurrency;

import java.util.HashSet;
import java.util.Set;

/**
 * Exercise - check-then-act on shared state.
 *
 * <p>Lesson: "Concurrency basics for parallel test runs". Tests: {@code IdempotencyGuardTest}. Run:
 * {@code mvn test -Dtest=IdempotencyGuardTest}
 *
 * <p>A payment service uses this guard so that a request with a given idempotency key is processed
 * once. It works when requests arrive one by one. When a client retries quickly and two copies of the
 * request arrive on different threads at the same moment, both get processed - a duplicate charge. Fix
 * it. Keep the call to {@code recordInDatabase} (a real system has to store the key), and don't make
 * requests with <em>different</em> keys wait for each other.
 */
public final class IdempotencyGuard {

  private final Set<String> seen = new HashSet<>();

  /**
   * True the first time a key is seen - the caller then processes the payment - and false for every
   * later call with the same key. Safe to call from many threads at once.
   */
  public boolean firstTime(String key) {
    if (seen.contains(key)) {
      return false;
    }
    recordInDatabase(key);
    seen.add(key);
    return true;
  }

  /** Stands in for a database round trip: it takes a little while. */
  static void recordInDatabase(String key) {
    try {
      Thread.sleep(20);
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
    }
  }
}
