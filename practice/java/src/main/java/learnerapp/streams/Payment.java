package learnerapp.streams;

/**
 * One payment attempt as the test framework records it. A retried payment keeps its id and gets a
 * higher attempt number.
 *
 * @param status PENDING, SUCCEEDED or FAILED
 * @param method card, bank-transfer or wallet
 */
public record Payment(String id, int attempt, String status, String method, String currency, long amountMinor) {}
