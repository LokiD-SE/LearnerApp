package learnerapp.streams;

import static java.util.stream.Collectors.counting;
import static java.util.stream.Collectors.groupingBy;
import static java.util.stream.Collectors.mapping;
import static java.util.stream.Collectors.toList;

import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.TreeMap;

/** Reference solution - one pipeline per question: a source, filters and maps, one terminal operation. */
public final class PaymentStats {

  private PaymentStats() {}

  public static long succeededTotal(List<Payment> payments, String currency) {
    return payments.stream()
        .filter(p -> p.status().equals("SUCCEEDED"))
        .filter(p -> p.currency().equals(currency))
        .mapToLong(Payment::amountMinor)
        .sum();
  }

  public static Map<String, Long> countByStatus(List<Payment> payments) {
    return payments.stream().collect(groupingBy(Payment::status, counting()));
  }

  public static Optional<Payment> largestFailed(List<Payment> payments) {
    return payments.stream()
        .filter(p -> p.status().equals("FAILED"))
        .max(Comparator.comparingLong(Payment::amountMinor));
  }

  public static Map<String, List<String>> idsByMethod(List<Payment> payments) {
    // the map factory decides the key order: TreeMap sorts the methods
    return payments.stream()
        .collect(groupingBy(Payment::method, TreeMap::new, mapping(Payment::id, toList())));
  }
}
