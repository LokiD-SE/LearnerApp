import { PGlite } from '@electric-sql/pglite';
import { refund } from '../../exercises/transactions/refunds.js';
import { createSchema } from '../../exercises/transactions/schema.js';

async function setup() {
  const db = new PGlite();
  await createSchema(db);
  await db.query(
    `INSERT INTO payments (id, currency, captured_minor) VALUES
       ('pay_1001', 'EUR', 10000),
       ('pay_1002', 'EUR', 5000)`,
  );
  return db;
}

async function state(db: PGlite, paymentId = 'pay_1001') {
  const payment = await db.query<{ refunded_minor: number }>(
    'SELECT refunded_minor FROM payments WHERE id = $1',
    [paymentId],
  );
  const refunds = await db.query<{ amount_minor: number }>(
    'SELECT amount_minor FROM refunds WHERE payment_id = $1 ORDER BY id',
    [paymentId],
  );
  const outbox = await db.query<{ event_type: string; payload: Record<string, unknown> }>(
    'SELECT event_type, payload FROM outbox ORDER BY id',
  );
  return {
    refundedMinor: payment.rows[0]?.refunded_minor,
    refunds: refunds.rows.map((r) => r.amount_minor),
    outbox: outbox.rows,
  };
}

describe('refund - transactions and concurrency', { tags: ['@exercise'] }, () => {
  test('a valid refund updates the total, adds the refund row and an outbox event', async () => {
    const db = await setup();
    const result = await refund(db, 'pay_1001', 2500, 'damaged item');
    expect(result).toEqual({ ok: true, refundId: expect.any(Number), refundedMinor: 2500 });
    const after = await state(db);
    expect(after.refundedMinor).toBe(2500);
    expect(after.refunds).toEqual([2500]);
    expect(after.outbox).toEqual([
      {
        event_type: 'refund.created',
        payload: {
          refundId: (result as { refundId: number }).refundId,
          paymentId: 'pay_1001',
          amountMinor: 2500,
          currency: 'EUR',
        },
      },
    ]);
  });

  test('refunds add up, and the running total is returned', async () => {
    const db = await setup();
    await refund(db, 'pay_1001', 4000, 'first');
    const second = await refund(db, 'pay_1001', 6000, 'rest');
    expect(second).toMatchObject({ ok: true, refundedMinor: 10000 });
    expect((await state(db)).refunds).toEqual([4000, 6000]);
  });

  test('more than the refundable amount is refused with what is left, and nothing changes', async () => {
    const db = await setup();
    await refund(db, 'pay_1001', 7000, 'first');
    const result = await refund(db, 'pay_1001', 3001, 'too much');
    expect(result).toEqual({ ok: false, reason: 'exceeds_refundable', refundableMinor: 3000 });
    const after = await state(db);
    expect(after.refundedMinor).toBe(7000);
    expect(after.refunds).toEqual([7000]);
    expect(after.outbox).toHaveLength(1);
  });

  test('an unknown payment is not_found', async () => {
    const db = await setup();
    expect(await refund(db, 'pay_9999', 100, 'x')).toEqual({ ok: false, reason: 'not_found' });
  });

  test.each([0, -100, 12.5, Number.NaN])(
    'amount %s is invalid and the database is not touched',
    async (amount) => {
      const db = await setup();
      const spy = vi.spyOn(db, 'query');
      const transaction = vi.spyOn(db, 'transaction');
      expect(await refund(db, 'pay_1001', amount, 'x')).toEqual({ ok: false, reason: 'invalid_amount' });
      expect(spy).not.toHaveBeenCalled();
      expect(transaction).not.toHaveBeenCalled();
    },
  );

  test('two refunds at the same time can never refund more than was captured', async () => {
    const db = await setup();
    const results = await Promise.all([
      refund(db, 'pay_1001', 6000, 'customer service'),
      refund(db, 'pay_1001', 6000, 'chargeback team'),
    ]);
    expect(results.filter((r) => r.ok)).toHaveLength(1);
    expect(results.filter((r) => !r.ok)).toEqual([
      { ok: false, reason: 'exceeds_refundable', refundableMinor: 4000 },
    ]);
    const after = await state(db);
    expect(after.refundedMinor).toBe(6000);
    expect(after.refunds).toEqual([6000]);
  });

  test('five small refunds at once all count - no lost update', async () => {
    const db = await setup();
    await Promise.all([1, 2, 3, 4, 5].map((n) => refund(db, 'pay_1002', 1000, `part ${n}`)));
    const after = await state(db, 'pay_1002');
    expect(after.refundedMinor).toBe(5000);
    expect(after.refunds).toEqual([1000, 1000, 1000, 1000, 1000]);
  });

  test('a failure half-way leaves no trace: no total change, no refund row, no event', async () => {
    const db = await setup();
    const failure = new Error('simulated crash after the refund row');
    await expect(
      refund(db, 'pay_1001', 2500, 'x', {
        afterRefundRow: async () => {
          throw failure;
        },
      }),
    ).rejects.toBe(failure);
    const after = await state(db);
    expect(after.refundedMinor).toBe(0);
    expect(after.refunds).toEqual([]);
    expect(after.outbox).toEqual([]);
  });

  test('the hook runs inside the transaction - it sees the uncommitted refund row', async () => {
    const db = await setup();
    let seen = -1;
    await refund(db, 'pay_1001', 2500, 'x', {
      afterRefundRow: async (tx) => {
        seen = (await tx.query<{ n: number }>('SELECT count(*)::int AS n FROM refunds')).rows[0]!.n;
      },
    });
    expect(seen).toBe(1);
  });

  test('the payment id is a parameter, not part of the SQL text', async () => {
    const db = await setup();
    const hostile = "pay_1001' OR '1'='1";
    expect(await refund(db, hostile, 100, 'x')).toEqual({ ok: false, reason: 'not_found' });
    expect((await state(db)).refundedMinor).toBe(0);
  });
});
