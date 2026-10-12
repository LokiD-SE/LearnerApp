package shop.receipt;

/** One line of a receipt: product name, quantity and unit price in minor units (cents). */
public record ReceiptLine(String name, int quantity, long unitMinor) {

  public long totalMinor() {
    return Math.multiplyExact(unitMinor, quantity);
  }
}
