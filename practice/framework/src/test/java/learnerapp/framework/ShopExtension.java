package learnerapp.framework;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.extension.AfterAllCallback;
import org.junit.jupiter.api.extension.AfterEachCallback;
import org.junit.jupiter.api.extension.BeforeAllCallback;
import org.junit.jupiter.api.extension.BeforeEachCallback;
import org.junit.jupiter.api.extension.ExtensionContext;
import org.junit.jupiter.api.extension.ExtensionContext.Namespace;
import org.junit.jupiter.api.extension.ParameterContext;
import org.junit.jupiter.api.extension.ParameterResolver;
import org.openqa.selenium.OutputType;
import org.openqa.selenium.TakesScreenshot;
import org.openqa.selenium.WebDriver;

/**
 * The JUnit side of the framework. A test class with {@code @ExtendWith(ShopExtension.class)} gets:
 *
 * <ul>
 *   <li>a shop: the local copy, served once per test class, or {@code -Dshop.url} if set;
 *   <li>a new browser for every test, closed afterwards even when the test fails;
 *   <li>evidence when a test fails: a screenshot and the page source in {@code target/evidence}.
 * </ul>
 *
 * Tests ask for what they need as parameters: {@code void pays(WebDriver driver, Shop shop)}.
 */
public final class ShopExtension
    implements BeforeAllCallback, AfterAllCallback, BeforeEachCallback, AfterEachCallback, ParameterResolver {

  private static final Namespace NAMESPACE = Namespace.create(ShopExtension.class);
  private static final Path EVIDENCE = Path.of("target", "evidence");

  @Override
  public void beforeAll(ExtensionContext context) throws IOException {
    String url = Config.shopUrl();
    if (url.isEmpty()) {
      ShopServer server = ShopServer.start(Config.shopDir());
      context.getStore(NAMESPACE).put(ShopServer.class, server);
      context.getStore(NAMESPACE).put(Shop.class, server.shop());
    } else {
      context.getStore(NAMESPACE).put(Shop.class, new Shop(url));
    }
  }

  @Override
  public void afterAll(ExtensionContext context) {
    ShopServer server = context.getStore(NAMESPACE).remove(ShopServer.class, ShopServer.class);
    if (server != null) server.close();
  }

  @Override
  public void beforeEach(ExtensionContext context) {
    context.getStore(NAMESPACE).put(WebDriver.class, Browser.start());
  }

  @Override
  public void afterEach(ExtensionContext context) {
    WebDriver driver = context.getStore(NAMESPACE).remove(WebDriver.class, WebDriver.class);
    if (driver == null) return;
    try {
      if (context.getExecutionException().isPresent()) saveEvidence(driver, context);
    } finally {
      driver.quit();
    }
  }

  @Override
  public boolean supportsParameter(ParameterContext parameter, ExtensionContext context) {
    Class<?> type = parameter.getParameter().getType();
    return type == WebDriver.class || type == Shop.class;
  }

  @Override
  public Object resolveParameter(ParameterContext parameter, ExtensionContext context) {
    // the store looks in the test's context first, then the class's
    return context.getStore(NAMESPACE).get(parameter.getParameter().getType());
  }

  /** A failed UI test without evidence is a failure nobody can analyse later. */
  private static void saveEvidence(WebDriver driver, ExtensionContext context) {
    String name = context.getRequiredTestClass().getSimpleName() + "-" + context.getRequiredTestMethod().getName();
    try {
      Files.createDirectories(EVIDENCE);
      Path screenshot = EVIDENCE.resolve(name + ".png");
      Files.write(screenshot, ((TakesScreenshot) driver).getScreenshotAs(OutputType.BYTES));
      Files.writeString(EVIDENCE.resolve(name + ".html"), driver.getPageSource());
      System.out.println("Evidence for " + name + ": " + screenshot.toAbsolutePath() + " (url " + driver.getCurrentUrl() + ")");
    } catch (IOException | RuntimeException e) {
      System.out.println("Could not save evidence for " + name + ": " + e);
    }
  }
}
