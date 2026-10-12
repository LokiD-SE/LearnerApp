package shop.receipt;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.List;
import org.junit.jupiter.api.Test;

class ReceiptFormatterTest {

  @Test
  void formatsLinesAndTotal() {
    String receipt =
        ReceiptFormatter.format(
            List.of(new ReceiptLine("Espresso beans 1 kg", 2, 1899), new ReceiptLine("Oat milk 1 L", 1, 249)));
    assertEquals("2 x Espresso beans 1 kg: 37.98\n1 x Oat milk 1 L: 2.49\nTotal: 40.47", receipt);
  }

  @Test
  void anEmptyReceiptIsJustTheTotal() {
    assertEquals("Total: 0.00", ReceiptFormatter.format(List.of()));
  }

  @Test
  void lineTotalsMultiplyExactly() {
    assertEquals(3798, new ReceiptLine("Espresso beans 1 kg", 2, 1899).totalMinor());
  }
}
