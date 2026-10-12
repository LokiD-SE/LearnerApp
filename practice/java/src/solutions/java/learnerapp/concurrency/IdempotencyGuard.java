package learnerapp.concurrency;

import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Reference solution - make "check and claim" one atomic step. Set.add returns false if the key was
 * already there; on a concurrent set (ConcurrentHashMap.newKeySet()) exactly one of several simultaneous
 * add calls for the same key returns true. The slow work happens after the claim, outside any lock, so
 * different keys don't wait for each other. (A synchronized method would also be correct, but would make
 * every request wait for every other one's database call.)
 */
public final class IdempotencyGuard {

  private final Set<String> seen = ConcurrentHashMap.newKeySet();

  public boolean firstTime(String key) {
    if (!seen.add(key)) {
      return false;
    }
    recordInDatabase(key);
    return true;
  }

  static void recordInDatabase(String key) {
    try {
      Thread.sleep(20);
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
    }
  }
}
