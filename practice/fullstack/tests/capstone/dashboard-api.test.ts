import request from 'supertest';
import type { PGlite } from '@electric-sql/pglite';
import { createDashboardApi } from '../../exercises/capstone/dashboard-api.js';
import { createDashboardDb, resetDashboardDb } from '../../exercises/capstone/dashboard-db.js';
import { PROBLEMS } from '../../exercises/capstone/refund-service.js';

// Merchant 1 (Asha Books, sid-asha) owns pay_1001, pay_1002 and pay_1003; merchant 2 owns pay_2001.
let db: PGlite;
let app: ReturnType<typeof createDashboardApi>;
const ASHA = 'sid=sid-asha';
const KEY = '"5b0c3a1e-4f7d-4a8e-9c2b-1d6e8f0a2c4b"';

beforeAll(async () => {
  db = await createDashboardDb();
});

beforeEach(async () => {
  await resetDashboardDb(db);
  app = createDashboardApi({
    db,
    sessions: new Map([
      ['sid-asha', 1],
      ['sid-ravi', 2],
    ]),
  });
});

afterAll(async () => {
  await db.close();
});

const refund = (paymentId: string, body: unknown, key: string | null = KEY) => {
  const req = request(app).post(`/api/payments/${paymentId}/refunds`).set('Cookie', ASHA);
  if (key !== null) req.set('Idempotency-Key', key);
  return req.send(body as object);
};

const isProblem = (res: request.Response, status: number, name: string): void => {
  expect(res.status).toBe(status);
  expect(res.headers['content-type']).toMatch(/^application\/problem\+json/);
  expect(res.body).toMatchObject({ type: `${PROBLEMS}${name}`, status });
};

describe('capstone dashboard API: sessions and the payments list', { tags: ['@exercise'] }, () => {
  test('without a session, /api answers 401 sign-in-required as a problem', async () => {
    isProblem(await request(app).get('/api/payments'), 401, 'sign-in-required');
    isProblem(await request(app).get('/api/payments').set('Cookie', 'sid=forged'), 401, 'sign-in-required');
  });

  test("lists only the merchant's own payments, newest first, with what is refundable", async () => {
    const res = await request(app).get('/api/payments').set('Cookie', ASHA);
    expect(res.status).toBe(200);
    expect(res.body.payments).toEqual([
      {
        id: 'pay_1002',
        amountMinor: 1250,
        currency: 'EUR',
        refundedMinor: 0,
        refundableMinor: 1250,
        createdAt: '2026-11-12T14:02:00Z',
      },
      {
        id: 'pay_1001',
        amountMinor: 5000,
        currency: 'EUR',
        refundedMinor: 0,
        refundableMinor: 5000,
        createdAt: '2026-11-10T09:15:00Z',
      },
      {
        id: 'pay_1003',
        amountMinor: 2599,
        currency: 'EUR',
        refundedMinor: 2599,
        refundableMinor: 0,
        createdAt: '2026-11-01T08:30:00Z',
      },
    ]);
  });

  test('no X-Powered-By header, and /healthz answers without a session', async () => {
    const res = await request(app).get('/healthz');
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ status: 'ok' });
    expect(res.headers['x-powered-by']).toBeUndefined();
  });
});

describe('capstone dashboard API: POST a refund', { tags: ['@exercise'] }, () => {
  test('201 with Location and the refund; the list shows the new refundable amount', async () => {
    const res = await refund('pay_1001', { amountMinor: 1500 });
    expect(res.status).toBe(201);
    expect(res.headers.location).toBe('/api/payments/pay_1001/refunds/1');
    expect(res.body).toMatchObject({
      refundId: 1,
      paymentId: 'pay_1001',
      amountMinor: 1500,
      refundableMinor: 3500,
    });
    const list = await request(app).get('/api/payments').set('Cookie', ASHA);
    expect(list.body.payments.find((p: { id: string }) => p.id === 'pay_1001').refundableMinor).toBe(3500);
  });

  test('a retry is replayed with Idempotent-Replayed: true - one refund only', async () => {
    const first = await refund('pay_1001', { amountMinor: 1500 });
    const retry = await refund('pay_1001', { amountMinor: 1500 });
    expect(retry.status).toBe(201);
    expect(retry.body).toEqual(first.body);
    expect(retry.headers['idempotent-replayed']).toBe('true');
    expect(first.headers['idempotent-replayed']).toBeUndefined();
    const n = await db.query<{ n: number }>('SELECT count(*)::integer AS n FROM refunds');
    expect(n.rows[0]!.n).toBe(1);
  });

  test('the same key with another amount is a 422 problem', async () => {
    await refund('pay_1001', { amountMinor: 1500 });
    isProblem(await refund('pay_1001', { amountMinor: 1600 }), 422, 'idempotency-key-reused');
  });

  test('a missing or invalid Idempotency-Key is a 400 problem, checked before the body', async () => {
    isProblem(await refund('pay_1001', { amountMinor: 1500 }, null), 400, 'idempotency-key-missing');
    isProblem(await refund('pay_1001', { amountMinor: 1500 }, ''), 400, 'idempotency-key-missing');
    isProblem(await refund('pay_1001', { amountMinor: 'lots' }, 'short'), 400, 'idempotency-key-invalid');
  });

  test('an invalid body is a 422 validation-error pointing at the field', async () => {
    const res = await refund('pay_1001', { amountMinor: 12.5 });
    isProblem(res, 422, 'validation-error');
    expect(res.body.errors).toEqual([expect.objectContaining({ pointer: '#/amountMinor' })]);
    isProblem(await refund('pay_1001', { amountMinor: 100, status: 'APPROVED' }), 422, 'validation-error');
    isProblem(await refund('pay_1001', {}), 422, 'validation-error');
  });

  test('a body that is not JSON: 415 for the wrong type, 400 malformed-json for broken JSON', async () => {
    const text = await request(app)
      .post('/api/payments/pay_1001/refunds')
      .set('Cookie', ASHA)
      .set('Idempotency-Key', KEY)
      .set('Content-Type', 'text/plain')
      .send('amountMinor=1500');
    isProblem(text, 415, 'unsupported-media-type');
    const broken = await request(app)
      .post('/api/payments/pay_1001/refunds')
      .set('Cookie', ASHA)
      .set('Idempotency-Key', KEY)
      .set('Content-Type', 'application/json')
      .send('{"amountMinor": 15');
    isProblem(broken, 400, 'malformed-json');
  });

  test("another merchant's payment is 404, and too large an amount is 409 with refundableMinor", async () => {
    isProblem(await refund('pay_2001', { amountMinor: 100 }), 404, 'payment-not-found');
    const tooMuch = await refund('pay_1002', { amountMinor: 1300 }, 'key-asha-too-much');
    isProblem(tooMuch, 409, 'refund-exceeds-refundable');
    expect(tooMuch.body.refundableMinor).toBe(1250);
  });

  test('an unexpected database error is a 500 problem that leaks nothing', async () => {
    await db.exec('ALTER TABLE refunds RENAME TO refunds_moved');
    const errors = vi.spyOn(console, 'error').mockImplementation(() => {});
    try {
      const res = await refund('pay_1001', { amountMinor: 100 });
      isProblem(res, 500, 'internal-error');
      expect(JSON.stringify(res.body)).not.toMatch(/refunds|relation|stack/i);
    } finally {
      errors.mockRestore();
      await db.exec('ALTER TABLE refunds_moved RENAME TO refunds');
    }
  });
});
