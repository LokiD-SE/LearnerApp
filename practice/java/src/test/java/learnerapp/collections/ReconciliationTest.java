package learnerapp.collections;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTimeoutPreemptively;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Random;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

@Tag("exercise")
class ReconciliationTest {

  @Test
  void findsOurPaymentsThatAreMissingFromTheReport() {
    List<String> ours = List.of("pay_1", "pay_2", "pay_3", "pay_4");
    List<String> theirs = List.of("pay_3", "pay_1", "pay_9");
    assertEquals(List.of("pay_2", "pay_4"), Reconciliation.missing(ours, theirs));
  }

  @Test
  void keepsOurOrderAndReportsEachIdOnce() {
    List<String> ours = List.of("pay_7", "pay_2", "pay_7", "pay_5", "pay_2");
    assertEquals(List.of("pay_7", "pay_2", "pay_5"), Reconciliation.missing(ours, List.of("pay_5x")));
  }

  @Test
  void nothingIsMissingWhenEverythingSettled() {
    assertEquals(List.of(), Reconciliation.missing(List.of("pay_1"), List.of("pay_1")));
    assertEquals(List.of(), Reconciliation.missing(List.of(), List.of("pay_1")));
  }

  @Test
  void reconcilesADayOfPaymentsInTime() {
    List<String> ours = new ArrayList<>();
    for (int i = 0; i < 200_000; i++) ours.add("pay_" + i);
    List<String> theirs = new ArrayList<>(ours.subList(1_000, ours.size()));
    Collections.shuffle(theirs, new Random(42));

    List<String> missing = assertTimeoutPreemptively(Duration.ofSeconds(3), () -> Reconciliation.missing(ours, theirs));

    assertEquals(ours.subList(0, 1_000), missing);
  }
}
