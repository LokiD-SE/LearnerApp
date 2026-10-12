package learnerapp.equality;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

@Tag("exercise")
class PaymentTest {

  @Test
  void evidenceIsStillFoundAfterTheStatusChanges() {
    Map<Payment, List<String>> evidence = new HashMap<>();
    Payment payment = new Payment("pay_81Fz", "PENDING");
    evidence.computeIfAbsent(payment, p -> new ArrayList<>()).add("request sent");

    payment.setStatus("SUCCEEDED");

    assertTrue(evidence.containsKey(payment), "the same object must still be found");
    evidence.computeIfAbsent(payment, p -> new ArrayList<>()).add("webhook received");
    assertEquals(1, evidence.size(), "no second entry for the same payment");
    assertEquals(List.of("request sent", "webhook received"), evidence.get(payment));
  }

  @Test
  void aSetStillContainsThePaymentAfterTheStatusChanges() {
    Set<Payment> seen = new HashSet<>();
    Payment payment = new Payment("pay_81Fz", "PENDING");
    seen.add(payment);
    payment.setStatus("FAILED");
    assertTrue(seen.contains(payment));
    assertTrue(seen.remove(payment), "and it can be removed");
  }

  @Test
  void twoObjectsForTheSamePaymentAreEqual() {
    Payment fromTheApi = new Payment("pay_81Fz", "SUCCEEDED");
    Payment fromTheTest = new Payment("pay_81Fz", "PENDING");
    assertEquals(fromTheApi, fromTheTest);
    assertEquals(fromTheApi.hashCode(), fromTheTest.hashCode());
  }

  @Test
  void differentPaymentsAreNotEqual() {
    assertNotEquals(new Payment("pay_81Fz", "PENDING"), new Payment("pay_93Qa", "PENDING"));
  }
}
