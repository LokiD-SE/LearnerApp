package learnerapp.equality;

import java.util.Objects;

/**
 * Exercise - make {@code Money} a value object.
 *
 * <p>Lesson: "equals, hashCode and why HashMap needs both". Tests: {@code MoneyTest}. Run: {@code mvn
 * test -Dtest=MoneyTest}
 *
 * <p>Two {@code Money} objects with the same amount and currency must be equal, and must behave as one
 * value in a {@code HashSet} and as one key in a {@code HashMap}. Add {@code equals} and {@code
 * hashCode}; keep the constructor and the accessors as they are.
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
  public String toString() {
    return minorUnits + " " + currency;
  }
}
