package learnerapp.exercises.appium;

import io.appium.java_client.android.options.UiAutomator2Options;
import java.time.Duration;
import org.openqa.selenium.Capabilities;

/**
 * Reference solution - UiAutomator2Options sets platformName (Android) and appium:automationName
 * (UiAutomator2) itself, and every setter writes the capability with its appium: prefix. A browser
 * session gets browserName instead of an app: the driver documentation says not to provide both.
 */
public final class AndroidSessions {

  public static final String APP_PACKAGE = "com.sandpay.demo";

  public static final String APP_ACTIVITY = ".MainActivity";

  private AndroidSessions() {}

  public static Capabilities forApp(String apkPath, String udid) {
    return new UiAutomator2Options()
        .setApp(apkPath)
        .setAppPackage(APP_PACKAGE)
        .setAppActivity(APP_ACTIVITY)
        .setUdid(udid)
        .setAutoGrantPermissions(true)
        .setNewCommandTimeout(Duration.ofSeconds(120));
  }

  public static Capabilities forChrome(String udid) {
    return new UiAutomator2Options().setUdid(udid).withBrowserName("Chrome");
  }
}
