package learnerapp.parallel;

import java.util.concurrent.atomic.AtomicLong;

/**
 * Reference solution - unique test data for parallel runs.
 *
 * <p>One atomic counter per factory gives each call its own number, whichever thread makes it, with no
 * locking. The run id keeps values from different runs (or CI jobs sharing a test environment) apart.
 */
public final class TestDataFactory {

  private final String runId;
  private final AtomicLong next = new AtomicLong();

  /** {@code runId} identifies this test run, for example the CI build number. */
  public TestDataFactory(String runId) {
    this.runId = runId;
  }

  /** A unique order reference for this run, formatted {@code ORD-<runId>-<number>}. */
  public String orderReference() {
    return "ORD-" + runId + "-" + next.incrementAndGet();
  }

  /** A unique customer email for this run, formatted {@code buyer+<runId>-<number>@example.com}. */
  public String customerEmail() {
    return "buyer+" + runId + "-" + next.incrementAndGet() + "@example.com";
  }
}
