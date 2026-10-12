package learnerapp.collections;

import java.util.List;
import java.util.Set;

/**
 * Reference solution - removeIf (Java 8+) removes matching elements safely. The for-each loop failed
 * because removing through the list, not through the loop's iterator, changes the list under the
 * iterator, which then throws ConcurrentModificationException. An explicit Iterator with
 * iterator.remove() works too.
 */
public final class RetryQueue {

  private RetryQueue() {}

  public static void removeSettled(List<String> pending, Set<String> settled) {
    pending.removeIf(settled::contains);
  }
}
