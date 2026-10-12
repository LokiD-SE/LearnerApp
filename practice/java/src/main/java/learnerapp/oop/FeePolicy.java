package learnerapp.oop;

/** How SandPay prices one payment method: the fee, in minor units, for an amount in minor units. */
@FunctionalInterface
public interface FeePolicy {

  long feeFor(long amountMinor);
}
