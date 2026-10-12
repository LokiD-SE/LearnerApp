package learnerapp.basics;

import java.math.BigDecimal;
import java.util.regex.Pattern;

/**
 * Reference solution - money as whole minor units (cents, paise) in a {@code long}.
 *
 * <p>Parsing goes through {@link BigDecimal}, which holds decimal fractions exactly, and {@code
 * longValueExact()} refuses results that do not fit. Adding uses {@link Math#addExact}, which throws
 * instead of wrapping around.
 */
public final class MinorUnits {

  /** Digits, optionally a dot and one or two digits. No sign, separators or exponent. */
  private static final Pattern AMOUNT = Pattern.compile("\\d+(\\.\\d{1,2})?");

  private MinorUnits() {}

  public static long parse(String amount) {
    if (amount == null || !AMOUNT.matcher(amount).matches()) {
      throw new IllegalArgumentException("Not an amount with at most two decimals: " + amount);
    }
    try {
      return new BigDecimal(amount).movePointRight(2).longValueExact();
    } catch (ArithmeticException tooLarge) {
      throw new IllegalArgumentException("Amount does not fit in a long: " + amount, tooLarge);
    }
  }

  public static long sum(long... amounts) {
    long total = 0;
    for (long amount : amounts) {
      total = Math.addExact(total, amount);
    }
    return total;
  }

  public static String format(long minorUnits) {
    return BigDecimal.valueOf(minorUnits, 2).toPlainString();
  }
}
