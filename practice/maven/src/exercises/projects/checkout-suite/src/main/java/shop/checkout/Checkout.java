package shop.checkout;

/** Checkout arithmetic, in minor units (cents). */
public final class Checkout {

  private Checkout() {}

  public static long totalWithFee(long amountMinor, long feeMinor) {
    if (amountMinor < 0 || feeMinor < 0) throw new IllegalArgumentException("Amounts must not be negative");
    return Math.addExact(amountMinor, feeMinor);
  }
}
