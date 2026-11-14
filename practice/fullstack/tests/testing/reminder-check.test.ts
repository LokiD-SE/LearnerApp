import { InMemoryPendingOrders, checkReminderService } from '../../exercises/testing/reminder-check.js';
import {
  PgPendingOrders,
  createReminderService,
  type PendingOrder,
  type PendingOrders,
} from '../../exercises/testing/reminders.js';
import { reminderMutants } from './reminder-mutants.js';

const T = Date.UTC(2026, 10, 14, 9, 0, 0);
const order = (id: string, createdAt: number, extra: Partial<PendingOrder> = {}): PendingOrder => ({
  id,
  customerEmail: `${id}@customer.example`,
  createdAt,
  status: 'PENDING',
  reminded: false,
  ...extra,
});

// The same contract tests run against the real repository and the fake. If the fake passes them,
// tests that use it say something about production.
const implementations: [string, () => Promise<PendingOrders>][] = [
  ['PostgreSQL (PgPendingOrders)', () => PgPendingOrders.create()],
  ['your fake (InMemoryPendingOrders)', async () => new InMemoryPendingOrders()],
];

describe('a fake that keeps the contract, and a check that catches bugs', { tags: ['@exercise'] }, () => {
  afterEach(() => {
    vi.useRealTimers(); // in case a check forgot
  });

  describe.each(implementations)('PendingOrders contract: %s', (_name, make) => {
    test('returns only PENDING, unreminded orders created at or before the cutoff', async () => {
      const repo = await make();
      await repo.add(order('ord_old', T - 1000));
      await repo.add(order('ord_edge', T));
      await repo.add(order('ord_new', T + 1));
      await repo.add(order('ord_paid', T - 1000));
      await repo.setStatus('ord_paid', 'PAID');
      await repo.add(order('ord_done', T - 1000, { reminded: true }));
      expect((await repo.dueForReminder(T)).map((o) => o.id)).toEqual(['ord_old', 'ord_edge']);
    });

    test('orders oldest first, then by id', async () => {
      const repo = await make();
      await repo.add(order('ord_b', T));
      await repo.add(order('ord_c', T - 5));
      await repo.add(order('ord_a', T));
      expect((await repo.dueForReminder(T)).map((o) => o.id)).toEqual(['ord_c', 'ord_a', 'ord_b']);
    });

    test('markReminded removes an order from the due list', async () => {
      const repo = await make();
      await repo.add(order('ord_a', T));
      await repo.markReminded('ord_a');
      expect(await repo.dueForReminder(T)).toEqual([]);
    });

    test('returns copies with every field, not live objects', async () => {
      const repo = await make();
      await repo.add(order('ord_a', T));
      const [first] = await repo.dueForReminder(T);
      expect(first).toEqual(order('ord_a', T));
      if (first) first.reminded = true;
      expect((await repo.dueForReminder(T)).map((o) => o.id)).toEqual(['ord_a']);
    });

    test('rejects a second order with the same id', async () => {
      const repo = await make();
      await repo.add(order('ord_a', T));
      await expect(repo.add(order('ord_a', T))).rejects.toThrow();
    });
  });

  test('your check passes against the real reminder service', async () => {
    await expect(checkReminderService(createReminderService)).resolves.toBeUndefined();
  });

  test.each(reminderMutants.map((m) => [m.bug, m] as const))(
    'your check rejects: %s',
    async (_bug, mutant) => {
      await expect(
        checkReminderService(mutant.create),
        'your check accepted this broken service - which expectation would have caught it?',
      ).rejects.toThrow();
    },
  );
});
