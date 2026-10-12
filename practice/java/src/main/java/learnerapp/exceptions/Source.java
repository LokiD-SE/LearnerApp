package learnerapp.exceptions;

import java.io.IOException;

/** Something lines are read from - a file, a socket, a report download. Must be closed after use. */
public interface Source extends AutoCloseable {

  /** The next line, or null at the end. */
  String read() throws IOException;

  @Override
  void close() throws IOException;
}
