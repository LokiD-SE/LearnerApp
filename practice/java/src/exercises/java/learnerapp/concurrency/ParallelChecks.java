package learnerapp.concurrency;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Callable;

/**
 * Exercise - running independent checks at the same time.
 *
 * <p>Lesson: "Concurrency basics for parallel test runs". Tests: {@code ParallelChecksTest}. Run:
 * {@code mvn test -Dtest=ParallelChecksTest}
 *
 * <p>After a deployment, a smoke suite runs independent checks (is the API up, does a sandbox payment
 * succeed, ...). Each check mostly waits on the network, so running them one after another wastes time.
 * Run them on a thread pool instead.
 */
public final class ParallelChecks {

  private ParallelChecks() {}

  /**
   * Runs every check on a pool of {@code threads} threads and returns their results in the same order
   * as {@code checks} - not in the order they finish. If a check throws, throws an {@code
   * IllegalStateException} whose cause is the check's own exception. The pool is always shut down.
   */
  public static List<String> runAll(List<Callable<String>> checks, int threads) {
    List<String> results = new ArrayList<>();
    for (Callable<String> check : checks) {
      try {
        results.add(check.call());
      } catch (Exception e) {
        throw new IllegalStateException("A check failed", e);
      }
    }
    return results;
  }
}
