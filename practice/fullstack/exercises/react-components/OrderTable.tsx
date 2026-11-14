import type { ReactElement } from 'react';
import type { Order } from './orders.js';
// import { formatAmount } from './orders.js';
// import { StatusBadge } from './StatusBadge.js';

export interface OrderTableProps {
  orders: Order[];
}

/**
 * Exercise 2 (solve exercise 1 first - the table uses StatusBadge).
 *
 * Render, inside `<section aria-label="Orders">`:
 * - when `orders` is empty: only `<p>No orders yet.</p>` - no table;
 * - when some orders are FAILED: first a `<p>` reading "1 failed payment" or "2 failed payments";
 *   when none failed, nothing at all in its place (watch out for a stray 0);
 * - a `<table>` with `<caption>Orders</caption>`, a header row (Order, Customer, Amount, Status, Note)
 *   and one row per order: the id in a `<th scope="row">`, the customer, `formatAmount(...)`, a
 *   `<StatusBadge>`, and an `<input>` labelled "Note for <id>" (aria-label) where support staff type
 *   a note. The note is not saved anywhere - it lives only in the input.
 *
 * The parent re-sorts `orders` (by amount, by status...). A note typed into an order's row must stay
 * with that order after a re-sort.
 */
export function OrderTable(_props: OrderTableProps): ReactElement {
  throw new Error('TODO: OrderTable');
}
