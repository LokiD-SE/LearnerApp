package learnerapp.streams;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.BinaryOperator;
import java.util.stream.Collectors;

/**
 * Reference solution - Collectors.toMap throws IllegalStateException on a duplicate key unless you give
 * it a merge function that decides which value wins. The fourth argument chooses the map: a
 * LinkedHashMap keeps the order in which ids first appeared.
 */
public final class LatestAttempts {

  private LatestAttempts() {}

  public static Map<String, Payment> byId(List<Payment> payments) {
    BinaryOperator<Payment> later = (a, b) -> b.attempt() > a.attempt() ? b : a;
    return payments.stream()
        .collect(Collectors.toMap(Payment::id, payment -> payment, later, LinkedHashMap::new));
  }
}
