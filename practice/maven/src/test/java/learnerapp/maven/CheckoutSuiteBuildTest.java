package learnerapp.maven;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import learnerapp.maven.MavenBuild.Counts;
import learnerapp.maven.MavenBuild.Result;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

/** Checks the checkout-suite exercise project: which tests each phase runs, and what a failure does. */
@Tag("exercise")
class CheckoutSuiteBuildTest {

  private final Path project = MavenBuild.project("checkout-suite");

  @Test
  void testRunsOnlyTheFastUnitTests() throws Exception {
    Result build = MavenBuild.run(project, "clean", "test");
    assertEquals(0, build.exitCode(), "mvn clean test must succeed. Maven said:\n" + build.tail());
    Counts unit = MavenBuild.reports(project, "surefire-reports");
    assertFalse(unit.classes().contains("ReportExportTest"), "the slow test must not run in mvn test: " + unit.classes());
    assertEquals(2, unit.tests(), "the two fast tests in CheckoutTest: " + unit.classes());
  }

  @Test
  void slowTestsCanBeSwitchedOnFromTheCommandLine() throws Exception {
    Result build = MavenBuild.run(project, "clean", "test", "-DexcludedGroups=");
    assertEquals(0, build.exitCode(), "mvn clean test -DexcludedGroups= must succeed. Maven said:\n" + build.tail());
    Counts unit = MavenBuild.reports(project, "surefire-reports");
    assertTrue(unit.classes().contains("ReportExportTest"), "-DexcludedGroups= must run the slow test too: " + unit.classes());
    assertEquals(3, unit.tests());
  }

  @Test
  void verifyAlsoRunsTheIntegrationTests() throws Exception {
    Result build = MavenBuild.run(project, "clean", "verify");
    assertEquals(0, build.exitCode(), "mvn clean verify must succeed. Maven said:\n" + build.tail());
    Counts integration = MavenBuild.reports(project, "failsafe-reports");
    assertTrue(integration.classes().contains("CheckoutIT"), "mvn verify must run CheckoutIT: " + integration.classes());
  }

  @Test
  void aFailingIntegrationTestFailsTheBuild() throws Exception {
    Result build = MavenBuild.run(project, "clean", "verify", "-Dcheckout.it.fail=true");
    assertNotEquals(0, build.exitCode(), "a failing integration test must fail mvn verify. Maven said:\n" + build.tail());
    Counts integration = MavenBuild.reports(project, "failsafe-reports");
    assertTrue(integration.failures() + integration.errors() > 0, "the failure must come from CheckoutIT itself");
  }
}
