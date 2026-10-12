package learnerapp.concurrency;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Callable;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

@Tag("exercise")
class ParallelChecksTest {

  private static Callable<String> check(String name, long millis) {
    return () -> {
      Thread.sleep(millis);
      return name + " ok";
    };
  }

  private static long millisToRun(Runnable action) {
    long start = System.nanoTime();
    action.run();
    return Duration.ofNanos(System.nanoTime() - start).toMillis();
  }

  @Test
  void returnsResultsInTheOrderOfTheChecks() {
    List<Callable<String>> checks = List.of(check("api", 300), check("payment", 50), check("webhook", 150));
    assertEquals(List.of("api ok", "payment ok", "webhook ok"), ParallelChecks.runAll(checks, 3));
  }

  @Test
  void runsChecksAtTheSameTime() {
    List<Callable<String>> checks = new ArrayList<>();
    for (int i = 0; i < 8; i++) checks.add(check("check-" + i, 300));
    long took = millisToRun(() -> assertEquals(8, ParallelChecks.runAll(checks, 8).size()));
    assertTrue(took < 1500, "8 checks of 300 ms on 8 threads, one after another would take 2400 ms - took " + took);
  }

  @Test
  void usesNoMoreThreadsThanAllowed() {
    List<Callable<String>> checks = new ArrayList<>();
    for (int i = 0; i < 4; i++) checks.add(check("check-" + i, 300));
    long took = millisToRun(() -> ParallelChecks.runAll(checks, 2));
    assertTrue(took >= 550, "4 checks of 300 ms on 2 threads need two rounds - took only " + took + " ms");
  }

  @Test
  void aFailingCheckFailsTheRunWithItsOwnException() {
    IOException down = new IOException("sandbox unreachable");
    List<Callable<String>> checks =
        List.of(
            check("api", 10),
            () -> {
              throw down;
            });
    IllegalStateException failure = assertThrows(IllegalStateException.class, () -> ParallelChecks.runAll(checks, 2));
    assertSame(down, failure.getCause(), "the cause must be the check's exception, not a wrapper");
  }
}
