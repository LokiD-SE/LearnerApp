package learnerapp.exercises.appium;

import org.openqa.selenium.Capabilities;
import org.openqa.selenium.remote.DesiredCapabilities;

/**
 * Exercise - capabilities for Appium sessions on Android.
 *
 * <p>Lesson: "Appium architecture, drivers and capabilities". Tests: {@code AndroidSessionsTest}. Run:
 * {@code mvn test -Dtest=AndroidSessionsTest} (no device or Appium server needed - the tests check the
 * capabilities a session would be created with).
 *
 * <p>This code was copied from an Appium 1 project. Appium 2 and 3 reject it: capabilities that are not
 * W3C standard ones need the {@code appium:} prefix. Rewrite both methods - the Appium Java client's
 * {@code UiAutomator2Options} does most of the work.
 */
public final class AndroidSessions {

  /** The (fictional) SandPay demo app. */
  public static final String APP_PACKAGE = "com.sandpay.demo";

  public static final String APP_ACTIVITY = ".MainActivity";

  private AndroidSessions() {}

  /**
   * The SandPay demo app ({@code apkPath}, on the Appium server's machine) on the device with this
   * {@code udid}, with the UiAutomator2 driver: start {@link #APP_PACKAGE} at {@link #APP_ACTIVITY},
   * grant the app's permissions automatically, and end the session after 120 seconds without a command.
   */
  public static Capabilities forApp(String apkPath, String udid) {
    DesiredCapabilities caps = new DesiredCapabilities();
    caps.setCapability("platformName", "Android");
    caps.setCapability("automationName", "UiAutomator2");
    caps.setCapability("app", apkPath);
    caps.setCapability("udid", udid);
    caps.setCapability("appPackage", APP_PACKAGE);
    caps.setCapability("appActivity", APP_ACTIVITY);
    caps.setCapability("autoGrantPermissions", true);
    caps.setCapability("newCommandTimeout", 120);
    return caps;
  }

  /**
   * Chrome on the device with this {@code udid}, with the UiAutomator2 driver - for testing the shop's
   * mobile web pages. A browser session, so no app.
   */
  public static Capabilities forChrome(String udid) {
    Capabilities caps = forApp("", udid);
    DesiredCapabilities browser = new DesiredCapabilities(caps);
    browser.setCapability("browserName", "Chrome");
    return browser;
  }
}
