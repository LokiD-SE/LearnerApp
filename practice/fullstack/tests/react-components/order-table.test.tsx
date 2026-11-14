// @vitest-environment jsdom
import { render, screen, within } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { OrderTable } from '../../exercises/react-components/OrderTable.js';
import { sampleOrders, type Order } from '../../exercises/react-components/orders.js';

const paidOnly: Order[] = sampleOrders.filter((order) => order.status !== 'FAILED');

describe('OrderTable', { tags: ['@exercise'] }, () => {
  it('shows only "No orders yet." when there are no orders', () => {
    render(<OrderTable orders={[]} />);
    const section = screen.getByRole('region', { name: 'Orders' });
    expect(within(section).getByText('No orders yet.')).toBeTruthy();
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('renders a captioned table with a header row and one row per order', () => {
    render(<OrderTable orders={sampleOrders} />);
    const table = screen.getByRole('table', { name: 'Orders' });
    const headers = within(table)
      .getAllByRole('columnheader')
      .map((cell) => cell.textContent);
    expect(headers).toEqual(['Order', 'Customer', 'Amount', 'Status', 'Note']);
    // the header row + three orders
    expect(within(table).getAllByRole('row')).toHaveLength(4);
  });

  it('shows each order with its id as the row header, customer, formatted amount and status words', () => {
    render(<OrderTable orders={sampleOrders} />);
    const rowHeader = screen.getByRole('rowheader', { name: 'ORD-1001' });
    const row = rowHeader.closest('tr');
    expect(row).not.toBeNull();
    const cells = within(row!)
      .getAllByRole('cell')
      .map((cell) => cell.textContent);
    expect(cells.slice(0, 3)).toEqual(['Asha Rao', 'INR 1,250.00', 'Paid']);
    expect(within(row!).getByRole('textbox', { name: 'Note for ORD-1001' })).toBeTruthy();
  });

  it('counts failed payments with the right plural', () => {
    const { rerender } = render(<OrderTable orders={sampleOrders} />);
    expect(screen.getByText('1 failed payment')).toBeTruthy();
    const twoFailed = sampleOrders.map((order) => ({ ...order, status: 'FAILED' as const })).slice(0, 2);
    rerender(<OrderTable orders={twoFailed} />);
    expect(screen.getByText('2 failed payments')).toBeTruthy();
  });

  it('renders nothing before the table when no payment failed - not even a 0', () => {
    render(<OrderTable orders={paidOnly} />);
    const section = screen.getByRole('region', { name: 'Orders' });
    const table = screen.getByRole('table');
    expect(section.childNodes[0]).toBe(table);
    expect(screen.queryByText(/failed/)).toBeNull();
  });

  it('keeps a note with its order when the parent re-sorts the list', async () => {
    const user = userEvent.setup();
    const [a, b, c] = sampleOrders as [Order, Order, Order];
    const { rerender } = render(<OrderTable orders={[a, b, c]} />);

    await user.type(screen.getByRole('textbox', { name: 'Note for ORD-1002' }), 'customer called');

    // Re-sorted: the order that was second is now last.
    rerender(<OrderTable orders={[c, a, b]} />);
    expect(screen.getByRole('textbox', { name: 'Note for ORD-1002' })).toHaveProperty(
      'value',
      'customer called',
    );
    expect(screen.getByRole('textbox', { name: 'Note for ORD-1003' })).toHaveProperty('value', '');
    expect(screen.getByRole('textbox', { name: 'Note for ORD-1001' })).toHaveProperty('value', '');
  });
});
