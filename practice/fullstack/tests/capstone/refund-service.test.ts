import type { PGlite } from '@electric-sql/pglite';
import { createDashboardDb, resetDashboardDb } from '../../exercises/capstone/dashboard-db.js';
import {
  createRefund,
  fingerprintOf,
  PROBLEMS,
  type RefundCommand,
} from '../../exercises/capstone/refund-service.js';

// Merchant 1 (Asha Books) owns pay_1001 (5000), pay_1002 (1250) and pay_1003 (2599, fully refunded);
// merchant 2 (Ravi Electronics) owns pay_2001 (89900).
let db: PGlite;

beforeAll(async () => {
  db = await createDashboardDb();
});

beforeEach(async () => {
  await resetDashboardDb(db);
});

afterAll(async () => {
  await db.close();
});

const command = (overrides: Partial<RefundCommand> = {}): RefundCommand => ({
  merchantId: 1,
  paymentId: 'pay_1001',
  amountMinor: 1500,
  idempotencyKey: 'key-asha-0001',
  ...overrides,
});

const refundRows = async (): Promise<number> =>
  (await db.query<{ n: number }>('SELECT count(*)::integer AS n FROM refunds')).rows[0]!.n;
const refunded = async (paymentId: string): Promise<number> =>
  (
    await db.query<{ r: number }>('SELECT refunded_minor::integer AS r FROM payments WHERE id = $1', [
      paymentId,
    ])
  ).rows[0]!.r;

describe('capstone refund service: the refund', { tags: ['@exercise'] }, () => {
  test('a first request refunds: 201, one refund row, refunded_minor grows', async () => {
    const res = await createRefund(db, command());
    expect(res).toEqual({
      status: 201,
      replayed: false,
      body: { refundId: 1, paymentId: 'pay_1001', amountMinor: 1500, currency: 'EUR', refundableMinor: 3500 },
    });
    expect(await refundRows()).toBe(1);
    expect(await refunded('pay_1001')).toBe(1500);
  });

  test("another merchant's payment is not found and is not touched", async () => {
    const res = await createRefund(db, command({ paymentId: 'pay_2001' }));
    expect(res.status).toBe(404);
    expect(res.body).toMatchObject({ type: `${PROBLEMS}payment-not-found`, status: 404 });
    expect(await refunded('pay_2001')).toBe(0);
    expect(await refundRows()).toBe(0);
  });

  test('more than is left answers 409 with what is refundable, and changes nothing', async () => {
    const res = await createRefund(db, command({ paymentId: 'pay_1002', amountMinor: 1251 }));
    expect(res.status).toBe(409);
    expect(res.body).toMatchObject({
      type: `${PROBLEMS}refund-exceeds-refundable`,
      status: 409,
      refundableMinor: 1250,
    });
    expect(await refunded('pay_1002')).toBe(0);
  });

  test('exactly what is left is accepted and leaves 0', async () => {
    const res = await createRefund(db, command({ paymentId: 'pay_1002', amountMinor: 1250 }));
    expect(res.status).toBe(201);
    expect(res.body.refundableMinor).toBe(0);
  });
});

describe('capstone refund service: idempotency', { tags: ['@exercise'] }, () => {
  test('a retry with the same key and body replays the first answer and refunds nothing more', async () => {
    const first = await createRefund(db, command());
    const retry = await createRefund(db, command());
    expect(retry).toEqual({ ...first, replayed: true });
    expect(await refundRows()).toBe(1);
    expect(await refunded('pay_1001')).toBe(1500);
  });

  test('the same key with a different amount answers 422 and changes nothing', async () => {
    await createRefund(db, command());
    const reused = await createRefund(db, command({ amountMinor: 900 }));
    expect(reused.status).toBe(422);
    expect(reused.body).toMatchObject({ type: `${PROBLEMS}idempotency-key-reused`, status: 422 });
    expect(await refundRows()).toBe(1);
    expect(await refunded('pay_1001')).toBe(1500);
  });

  test('keys are scoped to the merchant: the same key from merchant 2 is a new request', async () => {
    await createRefund(db, command());
    const ravi = await createRefund(db, command({ merchantId: 2, paymentId: 'pay_2001', amountMinor: 900 }));
    expect(ravi).toMatchObject({ status: 201, replayed: false, body: { paymentId: 'pay_2001' } });
    expect(await refunded('pay_2001')).toBe(900);
  });

  test('a business error is stored and replayed too', async () => {
    const first = await createRefund(db, command({ paymentId: 'pay_1003', amountMinor: 1 }));
    expect(first.status).toBe(409);
    const retry = await createRefund(db, command({ paymentId: 'pay_1003', amountMinor: 1 }));
    expect(retry).toEqual({ ...first, replayed: true });
  });

  test('a key whose outcome is not stored yet answers 409 request-in-progress', async () => {
    await db.query(
      "INSERT INTO idempotency_keys (merchant_id, key, fingerprint) VALUES (1, 'key-asha-0001', $1)",
      [fingerprintOf(command())],
    );
    const res = await createRefund(db, command());
    expect(res.status).toBe(409);
    expect(res.body).toMatchObject({ type: `${PROBLEMS}request-in-progress` });
    expect(await refundRows()).toBe(0);
  });

  test('a crash after the refund row keeps nothing, so the retry with the same key refunds once', async () => {
    const crash = async (): Promise<void> => {
      throw new Error('process killed');
    };
    await expect(createRefund(db, command(), { afterRefund: crash })).rejects.toThrow('process killed');
    expect(await refundRows()).toBe(0);
    expect(await refunded('pay_1001')).toBe(0);

    const retry = await createRefund(db, command());
    expect(retry).toMatchObject({ status: 201, replayed: false });
    expect(await refundRows()).toBe(1);
  });

  test('two requests with the same key at the same moment refund exactly once', async () => {
    const [a, b] = await Promise.all([createRefund(db, command()), createRefund(db, command())]);
    expect([a.status, b.status]).toEqual([201, 201]);
    expect(a.body.refundId).toBe(b.body.refundId);
    expect([a.replayed, b.replayed].sort()).toEqual([false, true]);
    expect(await refundRows()).toBe(1);
    expect(await refunded('pay_1001')).toBe(1500);
  });
});
