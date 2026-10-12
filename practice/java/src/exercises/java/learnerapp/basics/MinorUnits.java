package learnerapp.basics;

/**
 * Exercise - money as whole minor units (cents, paise) in a {@code long}.
 *
 * <p>Lesson: "Primitive and reference types". Tests: {@code MinorUnitsTest}. Run: {@code mvn test
 * -Dtest=MinorUnitsTest}
 *
 * <p>Amounts in this exercise have two decimal places in their currency (like EUR or INR). Do not use
 * {@code double} or {@code float} anywhere: the tests include amounts that binary floating point cannot
 * hold exactly.
 */
public final class MinorUnits {

  private MinorUnits() {}

  /**
   * Parses a non-negative amount into minor units: {@code "19.99"} is 1999, {@code "5"} is 500, {@code
   * "0.5"} is 50.
   *
   * <p>Accepted text: one or more digits, optionally followed by a dot and one or two digits.
   *
   * @throws IllegalArgumentException if the text is null, does not have that form (blank, negative,
   *     more than two decimals, separators, exponents...), or the result does not fit in a {@code long}
   */
  public static long parse(String amount) {
    throw new UnsupportedOperationException("TODO: implement parse");
  }

  /**
   * Adds amounts in minor units.
   *
   * @throws ArithmeticException if the total does not fit in a {@code long} - never wrap around silently
   */
  public static long sum(long... amounts) {
    throw new UnsupportedOperationException("TODO: implement sum");
  }

  /**
   * Formats minor units with exactly two decimals: 1999 is {@code "19.99"}, 5 is {@code "0.05"}, -250 is
   * {@code "-2.50"}.
   */
  public static String format(long minorUnits) {
    throw new UnsupportedOperationException("TODO: implement format");
  }
}
