package learnerapp.exercises;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Duration;
import java.util.List;
import java.util.Set;
import java.util.function.Supplier;
import learnerapp.exercises.appium.Contexts;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.openqa.selenium.TimeoutException;

/** No device needed: the tests hand in the context names a driver would report, over time. */
@Tag("exercise")
class ContextsTest {

  private static final String PACKAGE = "com.sandpay.demo";
  private static final Duration TIMEOUT = Duration.ofSeconds(5);

  /** Reports only NATIVE_APP until {@code afterMillis}, then also the given webviews. */
  private static Supplier<Set<String>> webviewsAppearAfter(long afterMillis, String... webviews) {
    long start = System.nanoTime();
    return () -> {
      boolean loaded = Duration.ofNanos(System.nanoTime() - start).toMillis() >= afterMillis;
      if (!loaded) return Set.of(Contexts.NATIVE);
      List<String> names = new java.util.ArrayList<>(List.of(webviews));
      names.add(Contexts.NATIVE);
      return Set.copyOf(names);
    };
  }

  @Test
  void picksTheAppsWebviewOnAndroid() {
    assertEquals(
        "WEBVIEW_" + PACKAGE,
        Contexts.waitForWebview(webviewsAppearAfter(0, "WEBVIEW_com.android.chrome", "WEBVIEW_" + PACKAGE), PACKAGE, TIMEOUT));
  }

  @Test
  void waitsForTheWebviewToAppear() {
    long start = System.nanoTime();
    String context = Contexts.waitForWebview(webviewsAppearAfter(1_000, "WEBVIEW_" + PACKAGE), PACKAGE, TIMEOUT);
    long took = Duration.ofNanos(System.nanoTime() - start).toMillis();
    assertEquals("WEBVIEW_" + PACKAGE, context);
    assertTrue(took >= 900, "the webview only exists after about a second - it must be waited for, took " + took + " ms");
  }

  @Test
  void acceptsTheOnlyWebviewWhenNamesAreNumbered() {
    assertEquals("WEBVIEW_1", Contexts.waitForWebview(webviewsAppearAfter(0, "WEBVIEW_1"), PACKAGE, TIMEOUT));
  }

  @Test
  void refusesToGuessBetweenSeveralUnknownWebviews() {
    long start = System.nanoTime();
    IllegalStateException e =
        assertThrows(
            IllegalStateException.class,
            () -> Contexts.waitForWebview(webviewsAppearAfter(0, "WEBVIEW_1", "WEBVIEW_2"), PACKAGE, TIMEOUT));
    assertTrue(e.getMessage().contains("WEBVIEW_1") && e.getMessage().contains("WEBVIEW_2"), e.getMessage());
    assertTrue(Duration.ofNanos(System.nanoTime() - start).toMillis() < 2_000, "an ambiguous list won't improve by waiting");
  }

  @Test
  void givesUpWhenNoWebviewAppears() {
    long start = System.nanoTime();
    assertThrows(
        TimeoutException.class,
        () -> Contexts.waitForWebview(() -> Set.of(Contexts.NATIVE), PACKAGE, Duration.ofMillis(800)));
    assertTrue(Duration.ofNanos(System.nanoTime() - start).toMillis() < 3_000);
  }
}
