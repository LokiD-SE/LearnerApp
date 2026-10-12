package learnerapp.collections;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.ArrayList;
import java.util.LinkedList;
import java.util.List;
import java.util.Set;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

@Tag("exercise")
class RetryQueueTest {

  @Test
  void removesSettledPaymentsInPlace() {
    List<String> pending = new ArrayList<>(List.of("pay_1", "pay_2", "pay_3", "pay_4", "pay_5"));
    RetryQueue.removeSettled(pending, Set.of("pay_1", "pay_4"));
    assertEquals(List.of("pay_2", "pay_3", "pay_5"), pending);
  }

  @Test
  void removesEveryCopyAndNeighbouringIds() {
    List<String> pending = new ArrayList<>(List.of("pay_1", "pay_1", "pay_2", "pay_3", "pay_1"));
    RetryQueue.removeSettled(pending, Set.of("pay_1", "pay_2"));
    assertEquals(List.of("pay_3"), pending);
  }

  @Test
  void worksForAnyModifiableList() {
    List<String> pending = new LinkedList<>(List.of("pay_1", "pay_2", "pay_3"));
    RetryQueue.removeSettled(pending, Set.of("pay_2"));
    assertEquals(List.of("pay_1", "pay_3"), pending);
  }

  @Test
  void leavesTheQueueAloneWhenNothingSettled() {
    List<String> pending = new ArrayList<>(List.of("pay_1", "pay_2"));
    RetryQueue.removeSettled(pending, Set.of());
    assertEquals(List.of("pay_1", "pay_2"), pending);
  }
}
