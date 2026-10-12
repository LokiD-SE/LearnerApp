package learnerapp.collections;

import java.util.ArrayList;
import java.util.List;

/**
 * Exercise - the right collection for the access pattern.
 *
 * <p>Lesson: "Choosing the right collection". Tests: {@code ReconciliationTest}. Run: {@code mvn test
 * -Dtest=ReconciliationTest}
 *
 * <p>{@link #missing} gives the right answer. With a day of real settlement data - 200,000 payments on
 * each side - it doesn't finish in time. Make it fast; keep what it returns.
 */
public final class Reconciliation {

  private Reconciliation() {}

  /**
   * The payment ids in {@code ours} that do not appear in {@code theirs} (the provider's settlement
   * report): in the order they appear in {@code ours}, each id once.
   */
  public static List<String> missing(List<String> ours, List<String> theirs) {
    List<String> missing = new ArrayList<>();
    for (String id : ours) {
      if (!theirs.contains(id) && !missing.contains(id)) {
        missing.add(id);
      }
    }
    return missing;
  }
}
