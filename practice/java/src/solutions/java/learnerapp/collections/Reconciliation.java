package learnerapp.collections;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * Reference solution - "is this id in the other list?" is a membership question, which a HashSet
 * answers in constant time on average, while List.contains scans the whole list. A LinkedHashSet removes
 * duplicates and keeps the first-seen order.
 */
public final class Reconciliation {

  private Reconciliation() {}

  public static List<String> missing(List<String> ours, List<String> theirs) {
    Set<String> settled = new HashSet<>(theirs);
    Set<String> missing = new LinkedHashSet<>();
    for (String id : ours) {
      if (!settled.contains(id)) missing.add(id);
    }
    return new ArrayList<>(missing);
  }
}
