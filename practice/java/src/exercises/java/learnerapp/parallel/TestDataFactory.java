package learnerapp.parallel;

/**
 * Exercise - unique test data for parallel runs.
 *
 * <p>Lesson: "Parallel runs and thread safety". Tests: {@code TestDataFactoryTest}. Run:
 * {@code mvn test -Dtest=TestDataFactoryTest}
 *
 * <p>Each test asks the factory for a fresh order reference and customer email, so that tests running
 * at the same time never share an order or a customer. The current version uses the clock, on the
 * idea that "timestamps are unique enough" - they are not: many calls happen within one millisecond,
 * and parallel tests call it at the same moment. Make every value unique within a run, also when many
 * threads call the factory at once. Keep the formats documented below.
 */
public final class TestDataFactory {

  private final String runId;

  /** {@code runId} identifies this test run, for example the CI build number. */
  public TestDataFactory(String runId) {
    this.runId = runId;
  }

  /** A unique order reference for this run, formatted {@code ORD-<runId>-<number>}. */
  public String orderReference() {
    return "ORD-" + runId + "-" + System.currentTimeMillis();
  }

  /** A unique customer email for this run, formatted {@code buyer+<runId>-<number>@example.com}. */
  public String customerEmail() {
    return "buyer+" + runId + "-" + System.currentTimeMillis() + "@example.com";
  }
}
