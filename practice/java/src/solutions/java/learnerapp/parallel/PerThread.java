package learnerapp.parallel;

import java.util.function.Consumer;
import java.util.function.Supplier;

/**
 * Reference solution - one resource per test thread.
 *
 * <p>A {@link ThreadLocal} keeps a separate value per thread. {@code release()} closes the calling
 * thread's value and calls {@code remove()} - test runners reuse threads from a pool, so a value left
 * behind would leak into the next test that runs on the same thread.
 *
 * @param <T> the resource, for example a WebDriver
 */
public final class PerThread<T> {

  private final Supplier<T> factory;
  private final Consumer<T> closer;
  private final ThreadLocal<T> instance = new ThreadLocal<>();

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
    T current = instance.get();
    if (current == null) {
      current = factory.get();
      instance.set(current);
    }
    return current;
  }

  /** Closes and forgets the calling thread's resource, if it has one; the next get() creates a new one. */
  public void release() {
    T current = instance.get();
    if (current == null) {
      return;
    }
    try {
      closer.accept(current);
    } finally {
      instance.remove();
    }
  }
}
