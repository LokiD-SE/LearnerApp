package shop.checkout;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

/** A slow test - stands in for an export of a whole day's data. Run it on demand, not on every build. */
@Tag("slow")
class ReportExportTest {

  @Test
  void exportsADayOfPayments() throws InterruptedException {
    Thread.sleep(500);
    long total = 0;
    for (int i = 0; i < 10_000; i++) total = Checkout.totalWithFee(total, 1);
    assertEquals(10_000, total);
  }
}
