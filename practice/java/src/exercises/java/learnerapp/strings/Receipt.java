package learnerapp.strings;

import java.math.BigDecimal;
import java.util.List;

/**
 * Exercise - building a long text efficiently.
 *
 * <p>Lesson: "Strings, immutability and StringBuilder". Tests: {@code ReceiptTest}. Run: {@code mvn
 * test -Dtest=ReceiptTest}
 *
 * <p>The output of {@link #render} is already right. A merchant's daily receipt export has 100,000
 * lines, and this version never finishes in time. Make it fast without changing what it returns.
 */
public final class Receipt {

  /** One receipt line: quantity, product name and the line total in minor units (cents). */
  public record Line(int quantity, String name, long totalMinor) {}

  private Receipt() {}

  /**
   * One row per line, {@code "2 x Espresso beans 1 kg: 37.98"}, each followed by a line break
   * ({@code \n}), then a last row {@code "Total: 40.47"} without a line break. An empty receipt is just
   * {@code "Total: 0.00"}.
   */
  public static String render(List<Line> lines) {
    String receipt = "";
    long total = 0;
    for (Line line : lines) {
      receipt += line.quantity() + " x " + line.name() + ": " + amount(line.totalMinor()) + "\n";
      total += line.totalMinor();
    }
    receipt += "Total: " + amount(total);
    return receipt;
  }

  private static String amount(long minor) {
    return BigDecimal.valueOf(minor, 2).toPlainString();
  }
}
