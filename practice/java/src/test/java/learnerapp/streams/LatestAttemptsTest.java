package learnerapp.streams;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

@Tag("exercise")
class LatestAttemptsTest {

  @Test
  void mapsEachIdToItsPayment() {
    Payment one = new Payment("pay_1", 1, "SUCCEEDED", "card", "EUR", 1999);
    Payment two = new Payment("pay_2", 1, "FAILED", "card", "EUR", 500);
    assertEquals(Map.of("pay_1", one, "pay_2", two), LatestAttempts.byId(List.of(one, two)));
  }

  @Test
  void keepsTheLatestAttemptOfARetriedPayment() {
    Payment first = new Payment("pay_1", 1, "FAILED", "card", "EUR", 1999);
    Payment retry = new Payment("pay_1", 2, "SUCCEEDED", "card", "EUR", 1999);
    assertEquals(Map.of("pay_1", retry), LatestAttempts.byId(List.of(first, retry)));
    assertEquals(Map.of("pay_1", retry), LatestAttempts.byId(List.of(retry, first)), "whatever the list order");
  }

  @Test
  void keepsTheOrderInWhichIdsFirstAppear() {
    List<Payment> payments =
        List.of(
            new Payment("pay_9", 1, "FAILED", "card", "EUR", 100),
            new Payment("pay_2", 1, "SUCCEEDED", "card", "EUR", 200),
            new Payment("pay_9", 2, "SUCCEEDED", "card", "EUR", 100),
            new Payment("pay_5", 1, "PENDING", "wallet", "EUR", 300));
    assertEquals(List.of("pay_9", "pay_2", "pay_5"), new ArrayList<>(LatestAttempts.byId(payments).keySet()));
  }
}
