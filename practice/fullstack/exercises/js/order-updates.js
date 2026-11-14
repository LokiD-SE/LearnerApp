// Order updates for the SandPay merchant dashboard (fictional). Plain JavaScript with JSDoc types,
// checked by TypeScript (checkJs). Lesson: Modern JavaScript - scope, closures, modules and async.
//
// The dashboard keeps orders in state that React compares by reference, so an update must return a
// NEW order and must never change the one it was given - not even its nested arrays or objects.

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
 * The original order and its `history` array must stay exactly as they were.
 * @param {Order} order
 * @param {string} status
 * @param {string} at ISO timestamp of the change
 * @returns {Order}
 */
export function withStatus(order, status, at) {
  throw new Error('TODO: return a new order - do not mutate the one given');
}

/**
 * The name to show for an order's customer: the customer's name if there is one - even an empty
 * string, which the merchant typed on purpose - otherwise 'Guest'. `customer` may be missing or null.
 * @param {Order} order
 * @returns {string}
 */
export function customerLabel(order) {
  throw new Error('TODO: use optional chaining and nullish coalescing');
}

/**
 * The order's currency, defaulting to 'EUR' when it is missing (undefined or null).
 * @param {Order} order
 * @returns {string}
 */
export function currencyOf(order) {
  throw new Error('TODO');
}
