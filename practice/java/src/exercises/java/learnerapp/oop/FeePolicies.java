package learnerapp.oop;

/**
 * Exercise - one policy per payment method, chosen once.
 *
 * <p>Lesson: "Encapsulation, inheritance, polymorphism and abstraction". Tests: {@code
 * FeePoliciesTest}. Run: {@code mvn test -Dtest=FeePoliciesTest}
 *
 * <p>SandPay's (fictional) prices:
 *
 * <ul>
 *   <li>{@code card}: 1.5% of the amount plus 25, the percentage rounded half up to a whole minor unit;
 *   <li>{@code bank-transfer}: 50, whatever the amount;
 *   <li>{@code wallet}: 1% of the amount rounded half up, but at least 10.
 * </ul>
 *
 * Write each rule as its own {@link FeePolicy} - a class or a lambda - and make {@link #forMethod}
 * return the right one. Code that charges fees will only ever see a {@code FeePolicy}; adding a payment
 * method later should mean adding a policy, not editing the others.
 */
public final class FeePolicies {

  private FeePolicies() {}

  /**
   * The fee policy for a payment method.
   *
   * @throws IllegalArgumentException for an unknown method
   */
  public static FeePolicy forMethod(String method) {
    throw new UnsupportedOperationException("TODO: return the policy for " + method);
  }
}
