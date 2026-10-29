package learnerapp.strings;

import java.util.Arrays;
import java.util.List;
import java.util.regex.Pattern;

/**
 * Reference solution. Three bugs hid in one line:
 *
 * <ul>
 *   <li>{@code split} takes a regular expression, and {@code |} means "or" - an empty pattern that
 *       splits between every character. Quote it: {@code "\\|"} or {@code Pattern.quote("|")}.
 *   <li>{@code split} drops trailing empty strings unless the limit is negative.
 *   <li>{@code trim} removes only characters up to U+0020; {@code strip} (Java 11+) removes the white space
 *       {@code Character.isWhitespace} defines (not the no-break spaces such as U+00A0).
 * </ul>
 */
public final class ReportLine {

  private static final Pattern SEPARATOR = Pattern.compile(Pattern.quote("|"));

  private ReportLine() {}

  public static List<String> fields(String line) {
    if (line == null) throw new IllegalArgumentException("line is null");
    return Arrays.stream(SEPARATOR.split(line, -1)).map(String::strip).toList();
  }
}
