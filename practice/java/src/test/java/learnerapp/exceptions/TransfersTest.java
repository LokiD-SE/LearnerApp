package learnerapp.exceptions;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.io.IOException;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

@Tag("exercise")
class TransfersTest {

  private final List<String> events = new ArrayList<>();

  private Source source(IOException failOnRead, String... lines) {
    Deque<String> remaining = new ArrayDeque<>(List.of(lines));
    return new Source() {
      @Override
      public String read() throws IOException {
        if (remaining.isEmpty() && failOnRead != null) throw failOnRead;
        return remaining.poll();
      }

      @Override
      public void close() {
        events.add("close source");
      }
    };
  }

  private Sink sink(IOException failOnWrite, IOException failOnClose) {
    return new Sink() {
      @Override
      public void write(String line) throws IOException {
        if (failOnWrite != null) throw failOnWrite;
        events.add("write " + line);
      }

      @Override
      public void close() throws IOException {
        events.add("close sink");
        if (failOnClose != null) throw failOnClose;
      }
    };
  }

  @Test
  void copiesEveryLineThenClosesTheSinkAndTheSource() throws IOException {
    assertEquals(2, Transfers.copy(source(null, "a", "b"), sink(null, null)));
    assertEquals(List.of("write a", "write b", "close sink", "close source"), events);
  }

  @Test
  void closesBothWhenReadingFails() {
    IOException broken = new IOException("connection reset");
    IOException thrown = assertThrows(IOException.class, () -> Transfers.copy(source(broken, "a"), sink(null, null)));
    assertSame(broken, thrown);
    assertEquals(List.of("write a", "close sink", "close source"), events);
  }

  @Test
  void keepsTheWriteFailureAndAttachesTheCloseFailure() {
    IOException diskFull = new IOException("disk full");
    IOException closeFailed = new IOException("close failed");
    IOException thrown =
        assertThrows(IOException.class, () -> Transfers.copy(source(null, "a"), sink(diskFull, closeFailed)));
    assertSame(diskFull, thrown, "the exception that explains the failure must win");
    assertArrayEquals(new Throwable[] {closeFailed}, thrown.getSuppressed());
    assertEquals(List.of("close sink", "close source"), events);
  }

  @Test
  void closesTheSourceEvenWhenClosingTheSinkFails() {
    IOException closeFailed = new IOException("close failed");
    IOException thrown =
        assertThrows(IOException.class, () -> Transfers.copy(source(null, "a"), sink(null, closeFailed)));
    assertSame(closeFailed, thrown);
    assertEquals(List.of("write a", "close sink", "close source"), events);
  }
}
