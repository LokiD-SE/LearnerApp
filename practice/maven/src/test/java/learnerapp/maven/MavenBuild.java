package learnerapp.maven;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Stream;

/**
 * Runs Maven on one of the exercise projects and reads what happened. Test infrastructure, not an
 * exercise.
 */
final class MavenBuild {

  /** The result of one Maven run. */
  record Result(int exitCode, String output) {

    /** The last lines of Maven's output, to show in an assertion message. */
    String tail() {
      List<String> lines = output.lines().toList();
      return String.join("\n", lines.subList(Math.max(0, lines.size() - 40), lines.size()));
    }
  }

  /** Test counts summed over the XML reports in a reports folder (surefire or failsafe). */
  record Counts(int tests, int failures, int errors, int skipped, List<String> classes) {}

  private MavenBuild() {}

  /** The exercise project's folder: the unsolved one, or the reference solution with -Psolutions. */
  static Path project(String name) {
    String variant = System.getProperty("practice.variant", "exercises");
    Path dir = Path.of("src", variant, "projects", name).toAbsolutePath();
    if (!Files.isRegularFile(dir.resolve("pom.xml"))) {
      throw new IllegalStateException("No exercise project at " + dir);
    }
    return dir;
  }

  /** Runs Maven in batch mode in {@code project} with the given arguments. */
  static Result run(Path project, String... args) throws IOException, InterruptedException {
    List<String> command = new ArrayList<>();
    command.add(mavenExecutable());
    command.addAll(List.of("-B", "-ntp"));
    command.addAll(List.of(args));
    Process process =
        new ProcessBuilder(command).directory(project.toFile()).redirectErrorStream(true).start();
    String output = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
    if (!process.waitFor(5, TimeUnit.MINUTES)) {
      process.destroyForcibly();
      throw new IllegalStateException("Maven did not finish within 5 minutes");
    }
    return new Result(process.exitValue(), output);
  }

  /** Sums the test counts in project/target/<folder>, for example "surefire-reports". */
  static Counts reports(Path project, String folder) throws IOException {
    Path dir = project.resolve("target").resolve(folder);
    if (!Files.isDirectory(dir)) return new Counts(0, 0, 0, 0, List.of());
    Pattern suite = Pattern.compile("<testsuite [^>]*>");
    int tests = 0, failures = 0, errors = 0, skipped = 0;
    List<String> classes = new ArrayList<>();
    try (Stream<Path> files = Files.list(dir)) {
      for (Path file : files.filter(f -> f.getFileName().toString().matches("TEST-.*\\.xml")).sorted().toList()) {
        Matcher m = suite.matcher(Files.readString(file));
        if (!m.find()) continue;
        String header = m.group();
        int count = attribute(header, "tests");
        if (count == 0) continue;
        tests += count;
        failures += attribute(header, "failures");
        errors += attribute(header, "errors");
        skipped += attribute(header, "skipped");
        classes.add(textAttribute(header, "name").replaceAll(".*\\.", ""));
      }
    }
    return new Counts(tests, failures, errors, skipped, classes);
  }

  private static int attribute(String header, String name) {
    String value = textAttribute(header, name);
    return value.isEmpty() ? 0 : Integer.parseInt(value);
  }

  private static String textAttribute(String header, String name) {
    Matcher m = Pattern.compile("\\s" + name + "=\"([^\"]*)\"").matcher(header);
    return m.find() ? m.group(1) : "";
  }

  private static String mavenExecutable() {
    boolean windows = System.getProperty("os.name", "").toLowerCase().contains("win");
    String name = windows ? "mvn.cmd" : "mvn";
    String home = System.getProperty("maven.home", "");
    if (!home.isBlank() && !home.startsWith("${")) {
      Path candidate = Path.of(home, "bin", name);
      if (Files.isRegularFile(candidate)) return candidate.toString();
    }
    return name; // from the PATH
  }
}
