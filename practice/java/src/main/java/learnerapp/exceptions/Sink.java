package learnerapp.exceptions;

import java.io.IOException;

/** Something lines are written to - a file, an upload, an evidence store. Must be closed after use. */
public interface Sink extends AutoCloseable {

  void write(String line) throws IOException;

  @Override
  void close() throws IOException;
}
