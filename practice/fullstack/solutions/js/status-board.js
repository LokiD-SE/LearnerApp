// Closures and `this` in the SandPay merchant dashboard (fictional). Reference solution.

/**
 * @param {number} limit
 * @returns {{ recordFailure(orderId: string): number, remaining(orderId: string): number }}
 */
export function createAttemptTracker(limit) {
  // Each call creates a new Map; the returned functions close over it, and nothing else can reach it.
  /** @type {Map<string, number>} */
  const failures = new Map();
  /** @param {string} orderId */
  const remaining = (orderId) => Math.max(0, limit - (failures.get(orderId) ?? 0));
  return {
    recordFailure(orderId) {
      failures.set(orderId, (failures.get(orderId) ?? 0) + 1);
      return remaining(orderId);
    },
    remaining,
  };
}

/**
 * @typedef {{ orderId: string, status: string }} StatusUpdate
 * @typedef {{ subscribe(listener: (update: StatusUpdate) => void): void }} StatusFeed
 */

export class StatusBoard {
  /** @param {StatusFeed} feed */
  constructor(feed) {
    this.feed = feed;
    /** @type {Map<string, string>} */
    this.latest = new Map();
  }

  start() {
    // `this.handle` passed on its own is a plain function: the feed calls it without a receiver, and
    // in module (strict) code `this` is then undefined. The arrow function keeps this board's `this`.
    // (`this.feed.subscribe(this.handle.bind(this))` works too.)
    this.feed.subscribe((update) => this.handle(update));
  }

  /** @param {StatusUpdate} update */
  handle(update) {
    this.latest.set(update.orderId, update.status);
  }
}
