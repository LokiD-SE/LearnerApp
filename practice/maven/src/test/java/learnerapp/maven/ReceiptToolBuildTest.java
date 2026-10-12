package learnerapp.maven;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import javax.xml.parsers.DocumentBuilderFactory;
import learnerapp.maven.MavenBuild.Counts;
import learnerapp.maven.MavenBuild.Result;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;

/** Checks the receipt-tool exercise project: it builds, its three tests really run, JUnit is test-scoped. */
@Tag("exercise")
class ReceiptToolBuildTest {

  private final Path project = MavenBuild.project("receipt-tool");

  @Test
  void buildsAndReallyRunsItsTests() throws Exception {
    Result build = MavenBuild.run(project, "clean", "test");
    assertEquals(0, build.exitCode(), "mvn clean test must succeed. Maven said:\n" + build.tail());

    Counts counts = MavenBuild.reports(project, "surefire-reports");
    assertEquals(
        3,
        counts.tests(),
        "receipt-tool has 3 JUnit tests, but " + counts.tests() + " ran - a green build that runs no tests proves nothing");
    assertEquals(0, counts.failures() + counts.errors());
  }

  @Test
  void junitIsOnlyATestDependency() throws Exception {
    Document pom =
        DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(project.resolve("pom.xml").toFile());
    NodeList dependencies = pom.getElementsByTagName("dependency");
    boolean found = false;
    for (int i = 0; i < dependencies.getLength(); i++) {
      Element dependency = (Element) dependencies.item(i);
      if (!"junit-jupiter".equals(text(dependency, "artifactId"))) continue;
      if (dependency.getParentNode().getParentNode().getNodeName().equals("dependencyManagement")) continue;
      found = true;
      assertEquals("test", text(dependency, "scope"), "junit-jupiter is needed by tests only - give it test scope");
    }
    assertTrue(found, "the pom must still depend on junit-jupiter");
  }

  private static String text(Element parent, String child) {
    NodeList nodes = parent.getElementsByTagName(child);
    return nodes.getLength() == 0 ? "" : nodes.item(0).getTextContent().trim();
  }
}
