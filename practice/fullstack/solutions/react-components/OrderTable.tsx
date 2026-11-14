import type { ReactElement } from 'react';
import { formatAmount, type Order } from './orders.js';
import { StatusBadge } from './StatusBadge.js';

export interface OrderTableProps {
  orders: Order[];
}

export function OrderTable({ orders }: OrderTableProps): ReactElement {
  if (orders.length === 0) {
    return (
      <section aria-label="Orders">
        <p>No orders yet.</p>
      </section>
    );
  }

  const failed = orders.filter((order) => order.status === 'FAILED').length;

  return (
    <section aria-label="Orders">
      {/* A boolean on the left of &&: with `failed && ...` a count of 0 would render "0". */}
      {failed > 0 && (
        <p>
          {failed} failed {failed === 1 ? 'payment' : 'payments'}
        </p>
      )}
      <table>
        <caption>Orders</caption>
        <thead>
          <tr>
            <th scope="col">Order</th>
            <th scope="col">Customer</th>
            <th scope="col">Amount</th>
            <th scope="col">Status</th>
            <th scope="col">Note</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((order) => (
            // The order's id, not its index: the row - and the note typed into it - follows the
            // order when the list is re-sorted.
            <tr key={order.id}>
              <th scope="row">{order.id}</th>
              <td>{order.customer}</td>
              <td>{formatAmount(order.amountMinor, order.currency)}</td>
              <td>
                <StatusBadge status={order.status} />
              </td>
              <td>
                <input aria-label={`Note for ${order.id}`} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
