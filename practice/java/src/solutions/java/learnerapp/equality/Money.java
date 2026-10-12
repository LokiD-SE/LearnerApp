package learnerapp.equality;

import java.util.Objects;

/**
 * Reference solution - a value object: equal when the amount and the currency are equal.
 *
 * <p>Since Java 16 a record does all of this in one line: {@code record Money(long minorUnits, String
 * currency) {}} generates equals, hashCode and toString from the components.
 */
public final class Money {

  private final long minorUnits;
  private final String currency;

  public Money(long minorUnits, String currency) {
    this.minorUnits = minorUnits;
    this.currency = Objects.requireNonNull(currency, "currency");
  }

  public long minorUnits() {
    return minorUnits;
  }

  public String currency() {
    return currency;
  }

  @Override
  public boolean equals(Object other) {
    if (this == other) return true;
    // the class is final, so instanceof cannot let a subclass break symmetry
    if (!(other instanceof Money)) return false;
    Money that = (Money) other;
    return minorUnits == that.minorUnits && currency.equals(that.currency);
  }

  @Override
  public int hashCode() {
    // the same fields as equals, so equal objects always get equal hash codes
    return Objects.hash(minorUnits, currency);
  }

  @Override
  public String toString() {
    return minorUnits + " " + currency;
  }
}
