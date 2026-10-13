package learnerapp.parallel;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.function.Supplier;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

@Tag("exercise")
class TestDataFactoryTest {

  private static final int THREADS = 16;
  private static final int PER_THREAD = 500;

  /** Calls next PER_THREAD times on each of THREADS threads released together; returns every value. */
  private static List<String> fromManyThreads(Supplier<String> next) throws Exception {
    ExecutorService pool = Executors.newFixedThreadPool(THREADS);
    try {
      CountDownLatch ready = new CountDownLatch(THREADS);
      CountDownLatch go = new CountDownLatch(1);
      List<Future<List<String>>> futures = new ArrayList<>();
      for (int t = 0; t < THREADS; t++) {
        futures.add(
            pool.submit(
                () -> {
                  ready.countDown();
                  go.await();
                  List<String> values = new ArrayList<>(PER_THREAD);
                  for (int i = 0; i < PER_THREAD; i++) values.add(next.get());
                  return values;
                }));
      }
      ready.await();
      go.countDown();
      List<String> all = new ArrayList<>();
      for (Future<List<String>> future : futures) all.addAll(future.get());
      return all;
    } finally {
      pool.shutdownNow();
    }
  }

  @Test
  void referencesHaveTheDocumentedFormat() {
    String reference = new TestDataFactory("run42").orderReference();
    assertTrue(reference.matches("ORD-run42-\\d+"), reference);
  }

  @Test
  void emailsHaveTheDocumentedFormat() {
    String email = new TestDataFactory("run42").customerEmail();
    assertTrue(email.matches("buyer\\+run42-\\d+@example\\.com"), email);
  }

  @Test
  void consecutiveReferencesAreUnique() {
    TestDataFactory factory = new TestDataFactory("run42");
    Set<String> seen = new HashSet<>();
    for (int i = 0; i < 1_000; i++) {
      assertTrue(seen.add(factory.orderReference()), "duplicate reference after " + i + " calls");
    }
  }

  @Test
  void consecutiveEmailsAreUnique() {
    TestDataFactory factory = new TestDataFactory("run42");
    Set<String> seen = new HashSet<>();
    for (int i = 0; i < 1_000; i++) {
      assertTrue(seen.add(factory.customerEmail()), "duplicate email after " + i + " calls");
    }
  }

  @Test
  void referencesAreUniqueAcrossParallelThreads() throws Exception {
    TestDataFactory factory = new TestDataFactory("run42");
    List<String> all = fromManyThreads(factory::orderReference);
    Set<String> unique = ConcurrentHashMap.newKeySet();
    unique.addAll(all);
    assertEquals(THREADS * PER_THREAD, unique.size(), "some parallel tests got the same order reference");
  }

  @Test
  void differentRunsNeverCollide() {
    TestDataFactory first = new TestDataFactory("run41");
    TestDataFactory second = new TestDataFactory("run42");
    Set<String> seen = new HashSet<>();
    for (int i = 0; i < 100; i++) {
      assertTrue(seen.add(first.orderReference()));
      assertTrue(seen.add(second.orderReference()));
    }
  }
}
