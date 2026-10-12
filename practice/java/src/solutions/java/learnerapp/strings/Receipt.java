package learnerapp.strings;

import java.math.BigDecimal;
import java.util.List;

/**
 * Reference solution - one {@link StringBuilder}, appended to, turned into a String once.
 *
 * <p>{@code receipt += ...} in a loop builds a new String every time, copying everything so far: the
 * total work grows with the square of the number of lines. A StringBuilder grows one buffer instead.
 */
public final class Receipt {

  public record Line(int quantity, String name, long totalMinor) {}

  private Receipt() {}

  public static String render(List<Line> lines) {
    StringBuilder receipt = new StringBuilder(lines.size() * 40 + 20);
    long total = 0;
    for (Line line : lines) {
      receipt
          .append(line.quantity())
          .append(" x ")
          .append(line.name())
          .append(": ")
          .append(amount(line.totalMinor()))
          .append('\n');
      total = Math.addExact(total, line.totalMinor());
    }
    return receipt.append("Total: ").append(amount(total)).toString();
  }

  private static String amount(long minor) {
    return BigDecimal.valueOf(minor, 2).toPlainString();
  }
}
