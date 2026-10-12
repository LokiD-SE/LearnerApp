package learnerapp.exercises.appium;

import java.time.Duration;
import java.util.Collection;
import java.util.List;
import java.util.function.Supplier;
import org.openqa.selenium.support.ui.FluentWait;

/**
 * Reference solution - a FluentWait over the context list. FluentWait works with any input, not only a
 * WebDriver, which is what makes this testable without a device. Returning null means "not yet"; an
 * IllegalStateException is not ignored, so an ambiguous list ends the wait at once.
 */
public final class Contexts {

  public static final String NATIVE = "NATIVE_APP";

  private Contexts() {}

  public static String waitForWebview(Supplier<? extends Collection<String>> contexts, String appPackage, Duration timeout) {
    return new FluentWait<>(contexts)
        .withTimeout(timeout)
        .pollingEvery(Duration.ofMillis(250))
        .withMessage("a webview context for " + appPackage)
        .until(source -> choose(List.copyOf(source.get()), appPackage));
  }

  private static String choose(List<String> available, String appPackage) {
    String expected = "WEBVIEW_" + appPackage;
    if (available.contains(expected)) return expected;
    List<String> webviews = available.stream().filter(name -> name.startsWith("WEBVIEW_")).toList();
    if (webviews.size() == 1) return webviews.get(0);
    if (webviews.size() > 1) {
      throw new IllegalStateException("Several webviews and none for " + appPackage + ": " + available);
    }
    return null; // no webview yet - ask again
  }
}
