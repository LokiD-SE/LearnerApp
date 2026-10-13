package learnerapp.parallel;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotSame;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Set;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

@Tag("exercise")
class PerThreadTest {

  /** A stand-in for a browser session: it only remembers whether it was closed. */
  static final class FakeBrowser {
    final int id;
    volatile boolean closed;

    FakeBrowser(int id) {
      this.id = id;
    }
  }

  private final AtomicInteger created = new AtomicInteger();
  private final List<FakeBrowser> closed = Collections.synchronizedList(new ArrayList<>());

  private PerThread<FakeBrowser> holder() {
    return new PerThread<>(
        () -> new FakeBrowser(created.incrementAndGet()),
        browser -> {
          browser.closed = true;
          closed.add(browser);
        });
  }

  @Test
  void theSameThreadGetsTheSameInstance() {
    PerThread<FakeBrowser> browsers = holder();
    assertSame(browsers.get(), browsers.get());
    assertEquals(1, created.get());
  }

  @Test
  void anotherThreadGetsItsOwnInstance() throws Exception {
    PerThread<FakeBrowser> browsers = holder();
    FakeBrowser mine = browsers.get();
    ExecutorService other = Executors.newSingleThreadExecutor();
    try {
      FakeBrowser theirs = other.submit(browsers::get).get(5, TimeUnit.SECONDS);
      assertNotSame(mine, theirs, "two threads share one browser");
      assertEquals(2, created.get());
    } finally {
      other.shutdownNow();
    }
  }

  @Test
  void releaseClosesOnlyTheCallingThreadsInstance() throws Exception {
    PerThread<FakeBrowser> browsers = holder();
    FakeBrowser mine = browsers.get();
    ExecutorService other = Executors.newSingleThreadExecutor();
    try {
      FakeBrowser theirs = other.submit(browsers::get).get(5, TimeUnit.SECONDS);
      other.submit(browsers::release).get(5, TimeUnit.SECONDS);
      assertTrue(theirs.closed, "the other thread's browser should be closed");
      assertTrue(!mine.closed, "release on another thread closed this thread's browser");
      assertSame(mine, browsers.get(), "this thread's browser was replaced");
    } finally {
      other.shutdownNow();
    }
  }

  @Test
  void afterReleaseTheNextGetCreatesANewInstance() {
    PerThread<FakeBrowser> browsers = holder();
    FakeBrowser first = browsers.get();
    browsers.release();
    FakeBrowser second = browsers.get();
    assertTrue(first.closed);
    assertNotSame(first, second);
    assertEquals(List.of(first), closed);
  }

  @Test
  void releaseWithoutAnInstanceDoesNothing() {
    PerThread<FakeBrowser> browsers = holder();
    browsers.release();
    assertEquals(0, created.get(), "release should not create a browser just to close it");
    assertTrue(closed.isEmpty());
  }

  @Test
  void eightParallelThreadsEachGetAndCloseTheirOwn() throws Exception {
    PerThread<FakeBrowser> browsers = holder();
    int threads = 8;
    ExecutorService pool = Executors.newFixedThreadPool(threads);
    try {
      CountDownLatch allHaveOne = new CountDownLatch(threads);
      List<Future<FakeBrowser>> futures = new ArrayList<>();
      for (int i = 0; i < threads; i++) {
        futures.add(
            pool.submit(
                () -> {
                  FakeBrowser browser = browsers.get();
                  allHaveOne.countDown();
                  allHaveOne.await();          // nobody releases before everyone has a browser
                  FakeBrowser again = browsers.get();
                  browsers.release();
                  return browser == again ? browser : null;
                }));
      }
      Set<FakeBrowser> distinct = Collections.newSetFromMap(new IdentityHashMap<>());
      for (Future<FakeBrowser> future : futures) {
        FakeBrowser browser = future.get(10, TimeUnit.SECONDS);
        assertTrue(browser != null, "a thread's browser changed while it was using it");
        distinct.add(browser);
      }
      assertEquals(threads, distinct.size(), "threads shared browsers");
      assertEquals(threads, closed.size(), "every browser should be closed exactly once");
    } finally {
      pool.shutdownNow();
    }
  }
}
