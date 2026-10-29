package learnerapp.strings;

import java.util.Arrays;
import java.util.List;

/**
 * Exercise - splitting a report line correctly.
 *
 * <p>Lesson: "Strings, immutability and StringBuilder". Tests: {@code ReportLineTest}. Run: {@code mvn
 * test -Dtest=ReportLineTest}
 *
 * <p>This method looks finished and returns something for every input - but not the right thing. Run
 * the tests, read the failures, and fix it without changing the signature.
 */
public final class ReportLine {

  private ReportLine() {}

  /**
   * Splits one line of a SandPay settlement report into its fields. Fields are separated by {@code |}.
   * Each field is stripped of leading and trailing white space - Unicode white space as
   * {@code Character.isWhitespace} defines it, not only spaces. Empty fields are kept, including
   * empty fields at the end: {@code "a||"} has three fields, {@code "a"}, {@code ""} and {@code ""}.
   *
   * @throws IllegalArgumentException if {@code line} is null
   */
  public static List<String> fields(String line) {
    return Arrays.stream(line.split("|")).map(String::trim).toList();
  }
}
