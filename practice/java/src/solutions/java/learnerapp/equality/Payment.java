package learnerapp.equality;

import java.util.Objects;

/**
 * Reference solution - an entity is identified by its id, not by its changing state.
 *
 * <p>The original equals and hashCode included the status. A {@code HashMap} files a key under the
 * hash code it had when it was put; after the status changed, the hash code changed, so lookups
 * searched the wrong bucket. Equality on the immutable id keeps the hash code stable.
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
    return id.equals(((Payment) other).id);
  }

  @Override
  public int hashCode() {
    return id.hashCode();
  }

  @Override
  public String toString() {
    return id + " (" + status + ")";
  }
}
