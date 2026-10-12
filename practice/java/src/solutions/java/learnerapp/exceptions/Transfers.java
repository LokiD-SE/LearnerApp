package learnerapp.exceptions;

import java.io.IOException;

/**
 * Reference solution - try-with-resources. Resources declared in the header are closed automatically,
 * in reverse order (sink, then source), whether the block completes or throws. If the block throws and a
 * close throws too, the close's exception is added to the block's exception with addSuppressed.
 */
public final class Transfers {

  private Transfers() {}

  public static int copy(Source source, Sink sink) throws IOException {
    // Java 9+: existing (effectively final) variables can be listed; closed in reverse order
    try (source; sink) {
      int count = 0;
      String line;
      while ((line = source.read()) != null) {
        sink.write(line);
        count++;
      }
      return count;
    }
  }
}
