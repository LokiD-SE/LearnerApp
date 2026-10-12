package learnerapp.collections;

import java.util.List;
import java.util.Set;

/**
 * Exercise - removing while you iterate.
 *
 * <p>Lesson: "Choosing the right collection". Tests: {@code RetryQueueTest}. Run: {@code mvn test
 * -Dtest=RetryQueueTest}
 *
 * <p>A test framework keeps the ids of payments it still has to check. Once a payment has settled, its
 * id must leave the queue. {@link #removeSettled} crashes on most inputs. Fix it.
 */
public final class RetryQueue {

  private RetryQueue() {}

  /** Removes, in place, every id in {@code pending} that is also in {@code settled}. */
  public static void removeSettled(List<String> pending, Set<String> settled) {
    for (String id : pending) {
      if (settled.contains(id)) {
        pending.remove(id);
      }
    }
  }
}
