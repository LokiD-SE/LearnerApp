// Order updates for the SandPay merchant dashboard (fictional). Reference solution.

/**
 * @typedef {{ at: string, status: string }} HistoryEntry
 * @typedef {{ name?: string, email?: string }} Customer
 * @typedef {{
 *   id: string,
 *   status: string,
 *   amountMinor: number,
 *   currency?: string,
 *   customer?: Customer | null,
 *   history: readonly HistoryEntry[],
 * }} Order
 */

/**
 * Returns a copy of `order` with the new status and one more history entry `{ at, status }`.
 * @param {Order} order
 * @param {string} status
 * @param {string} at
 * @returns {Order}
 */
export function withStatus(order, status, at) {
  // Spread copies one level only, so the history array needs its own copy: a new array that
  // shares the old (unchanged) entries and adds the new one.
  return { ...order, status, history: [...order.history, { at, status }] };
}

/**
 * @param {Order} order
 * @returns {string}
 */
export function customerLabel(order) {
  // ?. stops at undefined or null; ?? only replaces undefined or null - '' is kept, unlike ||.
  return order.customer?.name ?? 'Guest';
}

/**
 * @param {Order} order
 * @returns {string}
 */
export function currencyOf(order) {
  return order.currency ?? 'EUR';
}
