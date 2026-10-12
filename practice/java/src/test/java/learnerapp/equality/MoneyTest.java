package learnerapp.equality;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

/** Checks the equals and hashCode contract (java.lang.Object) for Money. */
@Tag("exercise")
class MoneyTest {

  private final Money a = new Money(1999, "EUR");
  private final Money b = new Money(1999, "EUR");
  private final Money c = new Money(1999, "EUR");

  @Test
  void isEqualToItself() {
    assertEquals(a, a);
  }

  @Test
  void isEqualToAnotherObjectWithTheSameAmountAndCurrency() {
    assertEquals(a, b, "two separate objects holding the same value");
  }

  @Test
  void equalityIsSymmetricAndTransitive() {
    assertTrue(a.equals(b) && b.equals(a), "symmetric");
    assertTrue(a.equals(b) && b.equals(c) && a.equals(c), "transitive");
  }

  @Test
  void differsWhenTheAmountOrCurrencyDiffers() {
    assertNotEquals(a, new Money(2000, "EUR"));
    assertNotEquals(a, new Money(1999, "INR"));
  }

  @Test
  void isNeverEqualToNullOrToAnotherType() {
    assertNotEquals(null, a);
    assertTrue(!a.equals(null), "equals(null) must return false, not throw");
    assertTrue(!a.equals("1999 EUR"), "a String with the same text is not Money");
    assertTrue(!a.equals(1999L), "a bare number is not Money");
  }

  @Test
  void equalObjectsHaveEqualHashCodes() {
    assertEquals(a.hashCode(), b.hashCode());
    assertEquals(a.hashCode(), a.hashCode(), "stable across calls");
  }

  @Test
  void aHashSetKeepsOneCopyOfAValue() {
    Set<Money> set = new HashSet<>();
    set.add(a);
    set.add(b);
    assertEquals(1, set.size());
    assertTrue(set.contains(new Money(1999, "EUR")));
  }

  @Test
  void aHashMapFindsAValueWithAnEqualKey() {
    Map<Money, String> fees = new HashMap<>();
    fees.put(a, "standard fee");
    assertEquals("standard fee", fees.get(new Money(1999, "EUR")));
  }
}
