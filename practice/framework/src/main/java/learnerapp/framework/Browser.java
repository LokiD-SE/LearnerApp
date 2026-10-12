package learnerapp.framework;

import org.openqa.selenium.WebDriver;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;

/**
 * Starts a browser. Every test gets a new one, so no test can leak cookies, storage or a half-filled
 * form into the next.
 *
 * <p>Only Chrome, because only Chrome is needed so far. A second browser would be added here, chosen
 * by a {@link Config} setting - when a test needs it.
 */
public final class Browser {

  private Browser() {}

  public static WebDriver start() {
    ChromeOptions options = new ChromeOptions();
    if (Config.headless()) {
      options.addArguments("--headless=new");
    }
    options.addArguments("--window-size=1280,900");
    // No implicit wait: every wait in this framework is explicit (see the waits lesson).
    // Selenium Manager finds or downloads a chromedriver that matches the installed Chrome.
    return new ChromeDriver(options);
  }
}
