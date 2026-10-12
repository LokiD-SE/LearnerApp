package learnerapp.oop;

import java.util.Map;

/**
 * Reference solution - each rule is a separate {@link FeePolicy}, and a map chooses one by name. The
 * choice happens once; after that, callers use the policy without knowing which one it is
 * (polymorphism). A new method is one new entry.
 */
public final class FeePolicies {

  /** A percentage given in basis points (1% = 100), rounded half up, plus a fixed part. */
  record PercentPlusFixed(long basisPoints, long fixedMinor) implements FeePolicy {
    @Override
    public long feeFor(long amountMinor) {
      return percent(amountMinor, basisPoints) + fixedMinor;
    }
  }

  /** A percentage with a minimum fee. */
  record PercentWithMinimum(long basisPoints, long minimumMinor) implements FeePolicy {
    @Override
    public long feeFor(long amountMinor) {
      return Math.max(percent(amountMinor, basisPoints), minimumMinor);
    }
  }

  private static final Map<String, FeePolicy> POLICIES =
      Map.of(
          "card", new PercentPlusFixed(150, 25),
          "bank-transfer", amountMinor -> 50,
          "wallet", new PercentWithMinimum(100, 10));

  private FeePolicies() {}

  public static FeePolicy forMethod(String method) {
    // Map.of maps reject null lookups with NullPointerException, so check first
    FeePolicy policy = method == null ? null : POLICIES.get(method);
    if (policy == null) throw new IllegalArgumentException("Unknown payment method: " + method);
    return policy;
  }

  /** amount x basisPoints / 10,000, rounded half up, without floating point. */
  private static long percent(long amountMinor, long basisPoints) {
    return Math.floorDiv(Math.multiplyExact(amountMinor, basisPoints) + 5_000, 10_000);
  }
}
