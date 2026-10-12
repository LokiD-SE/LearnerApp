package learnerapp.exceptions;

import java.io.IOException;

/**
 * Exercise - closing resources, whatever happens.
 *
 * <p>Lesson: "Exceptions and resource management". Tests: {@code TransfersTest}. Run: {@code mvn test
 * -Dtest=TransfersTest}
 *
 * <p>{@link #copy} works when nothing goes wrong. When reading, writing or closing fails, it leaks
 * resources or loses the exception that explains the failure. Fix it.
 */
public final class Transfers {

  private Transfers() {}

  /**
   * Copies every line from {@code source} to {@code sink} and returns how many lines it copied.
   *
   * <p>Takes ownership of both: always closes both - the sink first, then the source - even when
   * reading, writing or closing fails. If the copy fails and closing fails too, the copy's exception is
   * thrown, with the closing exception attached to it as a suppressed exception.
   */
  public static int copy(Source source, Sink sink) throws IOException {
    int count = 0;
    String line;
    while ((line = source.read()) != null) {
      sink.write(line);
      count++;
    }
    sink.close();
    source.close();
    return count;
  }
}
