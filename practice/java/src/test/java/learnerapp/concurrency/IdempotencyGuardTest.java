package learnerapp.concurrency;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.function.IntFunction;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

@Tag("exercise")
class IdempotencyGuardTest {

  private static final int THREADS = 16;

  /** Calls firstTime on THREADS threads released at the same moment; returns how many got true. */
  private static long simultaneous(IdempotencyGuard guard, IntFunction<String> keyForThread) throws Exception {
    ExecutorService pool = Executors.newFixedThreadPool(THREADS);
    try {
      CountDownLatch ready = new CountDownLatch(THREADS);
      CountDownLatch go = new CountDownLatch(1);
      List<Future<Boolean>> results = new ArrayList<>();
      for (int i = 0; i < THREADS; i++) {
        String key = keyForThread.apply(i);
        results.add(
            pool.submit(
                () -> {
                  ready.countDown();
                  go.await();
                  return guard.firstTime(key);
                }));
      }
      ready.await();
      go.countDown();
      long firsts = 0;
      for (Future<Boolean> result : results) if (result.get()) firsts++;
      return firsts;
    } finally {
      pool.shutdownNow();
    }
  }

  @Test
  void aKeyIsFirstOnlyOnce() {
    IdempotencyGuard guard = new IdempotencyGuard();
    assertTrue(guard.firstTime("key-1"));
    assertFalse(guard.firstTime("key-1"));
    assertTrue(guard.firstTime("key-2"));
  }

  @Test
  void simultaneousRequestsWithTheSameKeyAreProcessedOnce() throws Exception {
    IdempotencyGuard guard = new IdempotencyGuard();
    assertEquals(1, simultaneous(guard, i -> "key-retry"), "exactly one thread may process the payment");
  }

  @Test
  void differentKeysDoNotWaitForEachOther() throws Exception {
    IdempotencyGuard guard = new IdempotencyGuard();
    long start = System.nanoTime();
    assertEquals(THREADS, simultaneous(guard, i -> "key-" + i));
    long millis = Duration.ofNanos(System.nanoTime() - start).toMillis();
    // one at a time would take THREADS x 20 ms = 320 ms
    assertTrue(millis < 200, "requests with different keys must not queue behind each other, took " + millis + " ms");
  }
}
