package learnerapp.exercises;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Set;
import learnerapp.exercises.appium.AndroidSessions;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.openqa.selenium.Capabilities;
import org.openqa.selenium.Platform;

/** No device or server needed: these tests check the capabilities a new session would be sent. */
@Tag("exercise")
class AndroidSessionsTest {

  /** The capability names the W3C WebDriver standard defines; everything else needs a vendor prefix. */
  private static final Set<String> W3C =
      Set.of(
          "browserName",
          "browserVersion",
          "platformName",
          "acceptInsecureCerts",
          "pageLoadStrategy",
          "proxy",
          "setWindowRect",
          "timeouts",
          "strictFileInteractability",
          "unhandledPromptBehavior",
          "userAgent",
          "webSocketUrl");

  private static void assertAllStandardOrPrefixed(Capabilities caps) {
    for (String name : caps.asMap().keySet()) {
      assertTrue(
          W3C.contains(name) || name.contains(":"),
          "'" + name + "' is not a W3C capability, so Appium 2 and later need it as 'appium:" + name + "'");
    }
  }

  @Test
  void appSessionUsesTheUiAutomator2DriverOnAndroid() {
    Capabilities caps = AndroidSessions.forApp("/builds/sandpay-demo.apk", "emulator-5554");
    assertEquals(Platform.ANDROID, caps.getPlatformName());
    assertTrue("UiAutomator2".equalsIgnoreCase(String.valueOf(caps.getCapability("appium:automationName"))));
  }

  @Test
  void appSessionNamesTheAppAndTheDevice() {
    Capabilities caps = AndroidSessions.forApp("/builds/sandpay-demo.apk", "emulator-5554");
    assertEquals("/builds/sandpay-demo.apk", caps.getCapability("appium:app"));
    assertEquals("emulator-5554", caps.getCapability("appium:udid"));
    assertEquals(AndroidSessions.APP_PACKAGE, caps.getCapability("appium:appPackage"));
    assertEquals(AndroidSessions.APP_ACTIVITY, caps.getCapability("appium:appActivity"));
    assertEquals(true, caps.getCapability("appium:autoGrantPermissions"));
    assertEquals(120L, ((Number) caps.getCapability("appium:newCommandTimeout")).longValue());
  }

  @Test
  void appSessionCapabilitiesAreStandardOrPrefixed() {
    assertAllStandardOrPrefixed(AndroidSessions.forApp("/builds/sandpay-demo.apk", "emulator-5554"));
  }

  @Test
  void chromeSessionIsABrowserSessionWithoutAnApp() {
    Capabilities caps = AndroidSessions.forChrome("emulator-5554");
    assertTrue("chrome".equalsIgnoreCase(caps.getBrowserName()), "browserName: " + caps.getBrowserName());
    assertEquals(Platform.ANDROID, caps.getPlatformName());
    assertTrue("UiAutomator2".equalsIgnoreCase(String.valueOf(caps.getCapability("appium:automationName"))));
    assertEquals("emulator-5554", caps.getCapability("appium:udid"));
    assertFalse(caps.asMap().containsKey("appium:app"), "don't send both an app and a browserName");
    assertFalse(caps.asMap().containsKey("app"), "don't send both an app and a browserName");
    assertAllStandardOrPrefixed(caps);
  }
}
