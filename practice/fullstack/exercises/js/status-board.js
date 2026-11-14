// Closures and `this` in the SandPay merchant dashboard (fictional). Plain JavaScript with JSDoc
// types, checked by TypeScript (checkJs). Lesson: Modern JavaScript - scope, closures, modules and async.

/**
 * Tracks failed payment attempts per order, so the dashboard can block an order after `limit`
 * failures. The counts must be private: nothing outside the returned object can read or change them.
 *
 * - `recordFailure(orderId)` counts one failure and returns how many attempts that order has left
 *   (never below 0).
 * - `remaining(orderId)` returns how many attempts are left without recording anything.
 * - Two trackers never share counts.
 * @param {number} limit
 * @returns {{ recordFailure(orderId: string): number, remaining(orderId: string): number }}
 */
export function createAttemptTracker(limit) {
  throw new Error('TODO: keep the counts in a variable the returned functions close over');
}

/**
 * @typedef {{ orderId: string, status: string }} StatusUpdate
 * @typedef {{ subscribe(listener: (update: StatusUpdate) => void): void }} StatusFeed
 */

/**
 * Keeps the latest status of every order from a live feed. This class has a bug: after `start()`,
 * the first update from the feed throws. Find it and fix it - keep `handle` as the method that
 * stores the update.
 */
export class StatusBoard {
  /** @param {StatusFeed} feed */
  constructor(feed) {
    this.feed = feed;
    /** @type {Map<string, string>} */
    this.latest = new Map();
  }

  start() {
    this.feed.subscribe(this.handle);
  }

  /** @param {StatusUpdate} update */
  handle(update) {
    this.latest.set(update.orderId, update.status);
  }
}
