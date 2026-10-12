package learnerapp.exercises.appium;

import java.time.Duration;
import java.util.Collection;
import java.util.function.Supplier;

/**
 * Exercise - finding the right webview context in a hybrid app.
 *
 * <p>Lesson: "Native, hybrid and WebView contexts". Tests: {@code ContextsTest}. Run: {@code mvn test
 * -Dtest=ContextsTest} (no device needed - the tests pass in the context names a driver would report).
 *
 * <p>Use it with a real driver like this: {@code driver.context(Contexts.waitForWebview(
 * driver::getContextHandles, appPackage, Duration.ofSeconds(10)))}.
 */
public final class Contexts {

  /** The native context, as Appium drivers name it. */
  public static final String NATIVE = "NATIVE_APP";

  private Contexts() {}

  /**
   * Waits until the app's webview context is available and returns its name. A webview context only
   * appears once the webview has loaded, so ask {@code contexts} repeatedly until {@code timeout}.
   *
   * <p>Which context is the app's webview:
   *
   * <ul>
   *   <li>{@code "WEBVIEW_" + appPackage} if it is there (how the UiAutomator2 driver names a webview
   *       of the app);
   *   <li>otherwise, if there is exactly one context whose name starts with {@code WEBVIEW_}, that one
   *       (the XCUITest driver uses names such as {@code WEBVIEW_1});
   *   <li>several {@code WEBVIEW_} contexts and none for the package: throw {@code
   *       IllegalStateException} at once, listing them - waiting longer won't make the choice clear.
   * </ul>
   *
   * @throws org.openqa.selenium.TimeoutException if no webview context appears within {@code timeout}
   */
  public static String waitForWebview(Supplier<? extends Collection<String>> contexts, String appPackage, Duration timeout) {
    return "WEBVIEW_" + appPackage;
  }
}
