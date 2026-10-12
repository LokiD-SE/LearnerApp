package learnerapp.basics;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;

@Tag("exercise")
class MinorUnitsTest {

  @Test
  void parsesWholeAndDecimalAmounts() {
    assertEquals(1999, MinorUnits.parse("19.99"));
    assertEquals(500, MinorUnits.parse("5"));
    assertEquals(50, MinorUnits.parse("0.5"));
    assertEquals(5, MinorUnits.parse("0.05"));
    assertEquals(120_000, MinorUnits.parse("1200.00"));
  }

  @Test
  void keepsEveryCentThatDoubleWouldLose() {
    // 1.15 * 100 is 114.99999999999999 in double arithmetic, and 0.29 * 100 is 28.999999999999996
    assertEquals(115, MinorUnits.parse("1.15"));
    assertEquals(29, MinorUnits.parse("0.29"));
    // more minor units than a double can count exactly (2^53 + 1)
    assertEquals(9_007_199_254_740_993L, MinorUnits.parse("90071992547409.93"));
  }

  @Test
  void addsDecimalAmountsExactly() {
    // 0.1 + 0.2 == 0.3 is false for doubles
    assertEquals(MinorUnits.parse("0.30"), MinorUnits.sum(MinorUnits.parse("0.10"), MinorUnits.parse("0.20")));
    assertEquals(0, MinorUnits.sum());
  }

  @ParameterizedTest(name = "rejects \"{0}\"")
  @NullAndEmptySource
  @ValueSource(strings = {" ", "-1.00", "1.005", "1,000.00", "abc", "1e3", ".5", "5.", " 5", "+5"})
  void rejectsTextThatIsNotAnAmount(String text) {
    assertThrows(IllegalArgumentException.class, () -> MinorUnits.parse(text));
  }

  @Test
  void rejectsAmountsTooLargeForALong() {
    assertEquals(Long.MAX_VALUE, MinorUnits.parse("92233720368547758.07"));
    assertThrows(IllegalArgumentException.class, () -> MinorUnits.parse("92233720368547758.08"));
    assertThrows(IllegalArgumentException.class, () -> MinorUnits.parse("99999999999999999999"));
  }

  @Test
  void sumRefusesToWrapAround() {
    assertThrows(ArithmeticException.class, () -> MinorUnits.sum(Long.MAX_VALUE, 1));
    assertThrows(ArithmeticException.class, () -> MinorUnits.sum(Long.MIN_VALUE, -1));
  }

  @Test
  void formatsWithTwoDecimals() {
    assertEquals("19.99", MinorUnits.format(1999));
    assertEquals("0.05", MinorUnits.format(5));
    assertEquals("0.00", MinorUnits.format(0));
    assertEquals("1200.00", MinorUnits.format(120_000));
    assertEquals("-2.50", MinorUnits.format(-250));
  }
}
