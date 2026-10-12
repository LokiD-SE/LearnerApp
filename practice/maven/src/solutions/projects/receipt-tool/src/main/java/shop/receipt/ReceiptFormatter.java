package shop.receipt;

import java.math.BigDecimal;
import java.util.List;

/** Formats receipt lines and the total as text. */
public final class ReceiptFormatter {

  private ReceiptFormatter() {}

  public static String format(List<ReceiptLine> lines) {
    StringBuilder out = new StringBuilder();
    long total = 0;
    for (ReceiptLine line : lines) {
      out.append("%d x %s: %s\n".formatted(line.quantity(), line.name(), amount(line.totalMinor())));
      total = Math.addExact(total, line.totalMinor());
    }
    return out.append("Total: ").append(amount(total)).toString();
  }

  static String amount(long minor) {
    return BigDecimal.valueOf(minor, 2).toPlainString();
  }
}
