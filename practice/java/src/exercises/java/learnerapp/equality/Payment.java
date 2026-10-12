package learnerapp.equality;

import java.util.Objects;

/**
 * Exercise - a payment that gets lost in a {@code HashMap}.
 *
 * <p>Lesson: "equals, hashCode and why HashMap needs both". Tests: {@code PaymentTest}. Run: {@code mvn
 * test -Dtest=PaymentTest}
 *
 * <p>A test framework keeps evidence per payment in a {@code HashMap<Payment, List<String>>}. Once a
 * payment's status changes from PENDING to SUCCEEDED, its evidence can no longer be found. Fix this
 * class so the framework always finds a payment by the payment it is. Keep {@code setStatus}: payments
 * really do change status.
 */
public final class Payment {

  private final String id;
  private String status;

  public Payment(String id, String status) {
    this.id = Objects.requireNonNull(id, "id");
    this.status = Objects.requireNonNull(status, "status");
  }

  public String id() {
    return id;
  }

  public String status() {
    return status;
  }

  public void setStatus(String status) {
    this.status = Objects.requireNonNull(status, "status");
  }

  @Override
  public boolean equals(Object other) {
    if (this == other) return true;
    if (!(other instanceof Payment)) return false;
    Payment that = (Payment) other;
    return id.equals(that.id) && status.equals(that.status);
  }

  @Override
  public int hashCode() {
    return Objects.hash(id, status);
  }

  @Override
  public String toString() {
    return id + " (" + status + ")";
  }
}
