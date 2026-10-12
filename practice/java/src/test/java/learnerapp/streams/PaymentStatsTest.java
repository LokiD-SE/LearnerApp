package learnerapp.streams;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

@Tag("exercise")
class PaymentStatsTest {

  private static final List<Payment> PAYMENTS =
      List.of(
          new Payment("pay_1", 1, "SUCCEEDED", "card", "EUR", 1999),
          new Payment("pay_2", 1, "FAILED", "wallet", "EUR", 4500),
          new Payment("pay_3", 1, "SUCCEEDED", "bank-transfer", "EUR", 12000),
          new Payment("pay_4", 1, "SUCCEEDED", "card", "INR", 50000),
          new Payment("pay_5", 1, "FAILED", "card", "EUR", 9000),
          new Payment("pay_6", 1, "PENDING", "card", "EUR", 700));

  @Test
  void sumsSucceededPaymentsPerCurrency() {
    assertEquals(13999, PaymentStats.succeededTotal(PAYMENTS, "EUR"));
    assertEquals(50000, PaymentStats.succeededTotal(PAYMENTS, "INR"));
    assertEquals(0, PaymentStats.succeededTotal(PAYMENTS, "JPY"));
  }

  @Test
  void countsEachStatus() {
    assertEquals(Map.of("SUCCEEDED", 3L, "FAILED", 2L, "PENDING", 1L), PaymentStats.countByStatus(PAYMENTS));
    assertEquals(Map.of(), PaymentStats.countByStatus(List.of()));
  }

  @Test
  void findsTheLargestFailure() {
    assertEquals(Optional.of(PAYMENTS.get(4)), PaymentStats.largestFailed(PAYMENTS));
    assertTrue(PaymentStats.largestFailed(PAYMENTS.subList(0, 1)).isEmpty());
  }

  @Test
  void groupsIdsByMethodInOrder() {
    Map<String, List<String>> byMethod = PaymentStats.idsByMethod(PAYMENTS);
    assertEquals(
        Map.of("bank-transfer", List.of("pay_3"), "card", List.of("pay_1", "pay_4", "pay_5", "pay_6"), "wallet", List.of("pay_2")),
        byMethod);
    assertEquals(List.of("bank-transfer", "card", "wallet"), new ArrayList<>(byMethod.keySet()), "methods in alphabetical order");
  }
}
