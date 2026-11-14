import type { CreateReminderService, OrderStatus, PendingOrder, PendingOrders } from './reminders.js';

/**
 * TODO 1: a fake - a working in-memory PendingOrders. The checker runs the same contract tests
 * against it and against the real PostgreSQL repository, so it must behave the same way
 * (read the comments on PendingOrders in reminders.ts).
 */
export class InMemoryPendingOrders implements PendingOrders {
  async add(order: PendingOrder): Promise<void> {
    throw new Error(`TODO: store ${order.id}`);
  }

  async setStatus(id: string, status: OrderStatus): Promise<void> {
    throw new Error(`TODO: set ${id} to ${status}`);
  }

  async dueForReminder(cutoff: number): Promise<PendingOrder[]> {
    throw new Error(`TODO: orders due at ${cutoff}`);
  }

  async markReminded(id: string): Promise<void> {
    throw new Error(`TODO: mark ${id}`);
  }
}

/**
 * TODO 2: a check of a reminder service. Build one with `create`, your fake and a spy mailer
 * (vi.fn), drive time with Vitest's fake timers, and assert with expect - so this function
 * resolves for the real createReminderService and rejects for each of the six broken versions the
 * checker passes in. Always switch back to real timers before you return or throw.
 */
export async function checkReminderService(create: CreateReminderService): Promise<void> {
  throw new Error(`TODO: check ${create.name || 'the service'}`);
}
