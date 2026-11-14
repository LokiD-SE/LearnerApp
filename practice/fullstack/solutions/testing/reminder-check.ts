import { expect, vi } from 'vitest';
import {
  CHECK_EVERY_MS,
  REMIND_AFTER_MS,
  type CreateReminderService,
  type Mailer,
  type OrderStatus,
  type PendingOrder,
  type PendingOrders,
} from './reminders.js';

/** A fake: a real, working implementation that takes a shortcut (memory instead of a database). */
export class InMemoryPendingOrders implements PendingOrders {
  private readonly orders = new Map<string, PendingOrder>();

  async add(order: PendingOrder): Promise<void> {
    if (this.orders.has(order.id)) throw new Error(`duplicate order id ${order.id}`); // like the primary key
    this.orders.set(order.id, { ...order });
  }

  async setStatus(id: string, status: OrderStatus): Promise<void> {
    const order = this.orders.get(id);
    if (order) order.status = status;
  }

  async dueForReminder(cutoff: number): Promise<PendingOrder[]> {
    return [...this.orders.values()]
      .filter((o) => o.status === 'PENDING' && !o.reminded && o.createdAt <= cutoff)
      .sort((a, b) => a.createdAt - b.createdAt || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0))
      .map((o) => ({ ...o })); // copies, as rows from a database would be
  }

  async markReminded(id: string): Promise<void> {
    const order = this.orders.get(id);
    if (order) order.reminded = true;
  }
}

const START = Date.UTC(2026, 10, 14, 9, 0, 0); // a fixed "now" makes every run identical
const minutes = (n: number) => n * 60_000;

const order = (id: string, createdAt: number): PendingOrder => ({
  id,
  customerEmail: `${id}@customer.example`,
  createdAt,
  status: 'PENDING',
  reminded: false,
});

export async function checkReminderService(create: CreateReminderService): Promise<void> {
  vi.useFakeTimers({ now: START });
  try {
    const orders = new InMemoryPendingOrders();
    // A spy mailer: records every call. The first send to ord_b fails once, the way a mail
    // provider's timeout would.
    let failOnceFor: string | undefined = 'ord_b';
    const send = vi.fn<Mailer['send']>(async (message) => {
      if (message.orderId === failOnceFor) {
        failOnceFor = undefined;
        throw new Error('mail provider timeout');
      }
    });
    const service = create({ orders, mailer: { send } });

    await orders.add(order('ord_a', START)); // due at exactly 30 minutes
    await orders.add(order('ord_b', START)); // due too, but the first send fails
    await orders.add(order('ord_c', START + minutes(1))); // due one minute later
    await orders.add(order('ord_paid', START));
    await orders.setStatus('ord_paid', 'PAID'); // paid orders are never reminded

    service.start();

    // Just before the boundary: nothing yet.
    await vi.advanceTimersByTimeAsync(REMIND_AFTER_MS - CHECK_EVERY_MS);
    expect(send, 'no reminder before 30 minutes').not.toHaveBeenCalled();

    // At exactly 30 minutes: ord_a is reminded, with the right message; ord_b's send fails.
    await vi.advanceTimersByTimeAsync(CHECK_EVERY_MS);
    expect(send, 'ord_a is due at exactly 30 minutes').toHaveBeenCalledWith({
      to: 'ord_a@customer.example',
      template: 'payment-reminder',
      orderId: 'ord_a',
    });
    expect(send).toHaveBeenCalledWith(expect.objectContaining({ orderId: 'ord_b' }));

    // One minute later: ord_b is retried, ord_c is now due, ord_a is not sent again.
    await vi.advanceTimersByTimeAsync(CHECK_EVERY_MS);
    const sentTo = () => send.mock.calls.map(([message]) => message.orderId);
    expect(sentTo(), 'one retry for ord_b, one reminder each for ord_a and ord_c').toEqual([
      'ord_a',
      'ord_b',
      'ord_b',
      'ord_c',
    ]);

    // Quiet afterwards, and stop() really stops: a new due order is never reminded.
    await vi.advanceTimersByTimeAsync(minutes(10));
    expect(sentTo(), 'no duplicates later').toHaveLength(4);
    service.stop();
    await orders.add(order('ord_late', START));
    await vi.advanceTimersByTimeAsync(minutes(10));
    expect(sentTo(), 'nothing is sent after stop()').toHaveLength(4);
    expect(sentTo()).not.toContain('ord_paid');
  } finally {
    vi.useRealTimers();
  }
}
