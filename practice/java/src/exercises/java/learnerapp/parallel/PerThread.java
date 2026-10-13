package learnerapp.parallel;

import java.util.function.Consumer;
import java.util.function.Supplier;

/**
 * Exercise - one resource per test thread.
 *
 * <p>Lesson: "Parallel runs and thread safety". Tests: {@code PerThreadTest}. Run:
 * {@code mvn test -Dtest=PerThreadTest}
 *
 * <p>A framework keeps each test's browser (or API client, or database connection) in a holder like
 * this one. With tests running one at a time it works. With tests running in parallel on several
 * threads, they share one instance - one test types into another test's browser, and one test's
 * clean-up closes the browser another test is still using. Give every thread its own instance, created
 * on first use, and make {@link #release()} close and forget only the calling thread's instance.
 *
 * @param <T> the resource, for example a WebDriver
 */
public final class PerThread<T> {

  private final Supplier<T> factory;
  private final Consumer<T> closer;
  private T instance;

  /**
   * @param factory creates a new resource
   * @param closer closes a resource, for example {@code WebDriver::quit}
   */
  public PerThread(Supplier<T> factory, Consumer<T> closer) {
    this.factory = factory;
    this.closer = closer;
  }

  /** The calling thread's resource, created on its first call. */
  public T get() {
    if (instance == null) {
      instance = factory.get();
    }
    return instance;
  }

  /** Closes and forgets the calling thread's resource, if it has one; the next get() creates a new one. */
  public void release() {
    if (instance != null) {
      closer.accept(instance);
      instance = null;
    }
  }
}
