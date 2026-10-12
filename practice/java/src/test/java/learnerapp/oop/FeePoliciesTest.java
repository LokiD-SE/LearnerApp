package learnerapp.oop;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

@Tag("exercise")
class FeePoliciesTest {

  @Test
  void cardIsOnePointFivePercentPlusTwentyFive() {
    FeePolicy card = FeePolicies.forMethod("card");
    assertEquals(175, card.feeFor(10_000));
    assertEquals(55, card.feeFor(1999), "29.985 rounds half up to 30, plus 25");
    assertEquals(25, card.feeFor(0));
  }

  @Test
  void bankTransferIsFlat() {
    FeePolicy bank = FeePolicies.forMethod("bank-transfer");
    assertEquals(50, bank.feeFor(1));
    assertEquals(50, bank.feeFor(1_000_000));
  }

  @Test
  void walletIsOnePercentWithAMinimum() {
    FeePolicy wallet = FeePolicies.forMethod("wallet");
    assertEquals(20, wallet.feeFor(1999), "19.99 rounds half up to 20");
    assertEquals(10, wallet.feeFor(500), "5 is below the minimum of 10");
    assertEquals(250, wallet.feeFor(25_000));
  }

  @Test
  void unknownMethodsAreRejected() {
    assertThrows(IllegalArgumentException.class, () -> FeePolicies.forMethod("cheque"));
    assertThrows(IllegalArgumentException.class, () -> FeePolicies.forMethod(null));
  }
}
