package learnerapp.strings;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTimeoutPreemptively;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import learnerapp.strings.Receipt.Line;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

@Tag("exercise")
class ReceiptTest {

  @Test
  void rendersEachLineAndTheTotal() {
    String receipt =
        Receipt.render(List.of(new Line(2, "Espresso beans 1 kg", 3798), new Line(1, "Oat milk 1 L", 249)));
    assertEquals("2 x Espresso beans 1 kg: 37.98\n1 x Oat milk 1 L: 2.49\nTotal: 40.47", receipt);
  }

  @Test
  void anEmptyReceiptIsJustTheTotal() {
    assertEquals("Total: 0.00", Receipt.render(List.of()));
  }

  @Test
  void rendersAHundredThousandLinesInTime() {
    List<Line> lines = new ArrayList<>();
    for (int i = 0; i < 100_000; i++) lines.add(new Line(1, "Filter papers (100)", 499));
    String receipt = assertTimeoutPreemptively(Duration.ofSeconds(3), () -> Receipt.render(lines));
    assertTrue(receipt.endsWith("Total: 499000.00"), receipt.substring(receipt.length() - 30));
    assertEquals(100_001, receipt.lines().count());
  }
}
