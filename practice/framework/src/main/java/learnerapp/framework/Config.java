package learnerapp.framework;

import java.nio.file.Path;
import java.time.Duration;

/**
 * Settings, read from system properties ({@code mvn test -Dname=value}) with defaults that work on a
 * laptop and in CI. One place, so a test never hard-codes a URL, a path or a timeout.
 *
 * <p>Added when the same suite had to run against the local shop and the published copy, with and
 * without a browser window.
 */
public final class Config {

  private Config() {}

  /**
   * A shop that is already running, for example {@code https://lokid-se.github.io/LearnerApp/shop/}.
   * Empty (the default): the tests serve {@link #shopDir()} themselves.
   */
  public static String shopUrl() {
    String url = System.getProperty("shop.url", "").trim();
    return url.isEmpty() || url.endsWith("/") ? url : url + "/";
  }

  /** The shop's files, served locally when {@link #shopUrl()} is empty. Default {@code ../shop}. */
  public static Path shopDir() {
    return Path.of(System.getProperty("shop.dir", "../shop")).toAbsolutePath().normalize();
  }

  /**
   * Run Chrome without a window. Default: headless in CI (the {@code CI} environment variable is
   * {@code true}), with a window on your computer so you can watch.
   */
  public static boolean headless() {
    String value = System.getProperty("headless");
    return value != null ? Boolean.parseBoolean(value) : "true".equalsIgnoreCase(System.getenv("CI"));
  }

  /** The longest any wait in the framework waits for the shop. Default 10 seconds. */
  public static Duration timeout() {
    return Duration.ofSeconds(Long.parseLong(System.getProperty("timeout.seconds", "10")));
  }
}
