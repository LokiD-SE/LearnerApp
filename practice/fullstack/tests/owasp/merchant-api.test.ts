import request from 'supertest';
import type { PGlite } from '@electric-sql/pglite';
import { createMerchantApi, type Session } from '../../exercises/owasp/merchant-api.js';
import { createSandpayDb } from '../../exercises/owasp/sandpay-db.js';

// Merchant 1 (Asha Books) owns orders 101 and 102; merchant 2 (Ravi Electronics) owns 201 and 202.
const DASHBOARD = 'https://dashboard.sandpay.example';
const ASHA = { sid: 'sid-asha', csrfToken: 'csrf-asha-7f3a9c1e5b' };

let db: PGlite;
let app: ReturnType<typeof createMerchantApi>;

// One database per file (PGlite takes a moment to start); refunds are cleared before every test.
beforeAll(async () => {
  db = await createSandpayDb();
});

beforeEach(async () => {
  await db.exec('DELETE FROM refunds');
  const sessions = new Map<string, Session>([
    [ASHA.sid, { merchantId: 1, csrfToken: ASHA.csrfToken }],
    ['sid-ravi', { merchantId: 2, csrfToken: 'csrf-ravi-2b8d4e6f0a' }],
  ]);
  app = createMerchantApi({ db, sessions, allowedOrigins: [DASHBOARD] });
});

afterAll(async () => {
  await db.close();
});

const asAsha = `sid=${ASHA.sid}`;
const refundCount = async (): Promise<number> =>
  (await db.query<{ n: number }>('SELECT count(*)::integer AS n FROM refunds')).rows[0]?.n ?? -1;

describe('merchant API: access control (A01)', { tags: ['@exercise'] }, () => {
  test('without a session, /orders answers 401', async () => {
    const res = await request(app).get('/orders/101');
    expect(res.status).toBe(401);
  });

  test('a merchant reads their own order', async () => {
    const res = await request(app).get('/orders/101').set('Cookie', asAsha);
    expect(res.status).toBe(200);
    expect(res.body).toMatchObject({ id: 101, merchantId: 1 });
  });

  test("another merchant's order answers 404 and leaks nothing (IDOR)", async () => {
    const res = await request(app).get('/orders/201').set('Cookie', asAsha);
    expect(res.status).toBe(404);
    expect(JSON.stringify(res.body)).not.toContain('karan@example.test');
  });
});

describe('merchant API: injection (A05)', { tags: ['@exercise'] }, () => {
  test('the search finds only the merchant’s own matching orders', async () => {
    const res = await request(app).get('/orders').query({ q: 'asha' }).set('Cookie', asAsha);
    expect(res.status).toBe(200);
    expect(res.body.orders.map((o: { id: number }) => o.id)).toEqual([102]);
  });

  test('a SQL injection payload is searched for as text, not run as SQL', async () => {
    const res = await request(app)
      .get('/orders')
      .query({ q: "x' OR merchant_id <> 0 --" })
      .set('Cookie', asAsha);
    expect(res.status).toBe(200);
    expect(res.body.orders).toEqual([]);
  });

  test('a quote in a normal search does not break the query', async () => {
    const res = await request(app).get('/orders').query({ q: "o'brien" }).set('Cookie', asAsha);
    expect(res.status).toBe(200);
    expect(res.body.orders).toEqual([]);
  });
});

describe('merchant API: XSS and security headers', { tags: ['@exercise'] }, () => {
  test('the receipt page shows a reflected reference as text, not markup', async () => {
    const res = await request(app).get('/receipt').query({ ref: '<script>alert(1)</script>' });
    expect(res.status).toBe(404);
    expect(res.text).not.toContain('<script>');
    expect(res.text).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
  });

  test('every response has nosniff, a CSP that forbids framing, and no X-Powered-By', async () => {
    for (const res of [await request(app).get('/receipt'), await request(app).get('/orders')]) {
      expect(res.headers['x-content-type-options']).toBe('nosniff');
      expect(res.headers['content-security-policy']).toMatch(/frame-ancestors 'none'/);
      expect(res.headers['content-security-policy']).toMatch(/default-src 'none'/);
      expect(res.headers['x-powered-by']).toBeUndefined();
    }
  });
});

describe('merchant API: CORS', { tags: ['@exercise'] }, () => {
  test('the dashboard origin may read responses with credentials', async () => {
    const res = await request(app).get('/orders/101').set('Cookie', asAsha).set('Origin', DASHBOARD);
    expect(res.headers['access-control-allow-origin']).toBe(DASHBOARD);
    expect(res.headers['access-control-allow-credentials']).toBe('true');
    expect(res.headers.vary).toMatch(/Origin/);
  });

  test('any other origin gets no CORS permission', async () => {
    const res = await request(app)
      .get('/orders/101')
      .set('Cookie', asAsha)
      .set('Origin', 'https://evil.example');
    expect(res.headers['access-control-allow-origin']).toBeUndefined();
    expect(res.headers['access-control-allow-credentials']).toBeUndefined();
  });
});

describe('merchant API: CSRF on refunds (A01)', { tags: ['@exercise'] }, () => {
  const refund = () =>
    request(app).post('/orders/101/refunds').set('Cookie', asAsha).send({ amountMinor: 500 });

  test('a refund without the CSRF token is refused with 403', async () => {
    const res = await refund();
    expect(res.status).toBe(403);
    expect(await refundCount()).toBe(0);
  });

  test('a refund with the wrong token is refused with 403', async () => {
    const res = await refund().set('X-CSRF-Token', 'csrf-ravi-2b8d4e6f0a');
    expect(res.status).toBe(403);
    expect(await refundCount()).toBe(0);
  });

  test('a cross-site request is refused even with the right token', async () => {
    const res = await refund().set('X-CSRF-Token', ASHA.csrfToken).set('Sec-Fetch-Site', 'cross-site');
    expect(res.status).toBe(403);
    expect(await refundCount()).toBe(0);
  });

  test('the dashboard’s own request with the token creates the refund', async () => {
    const res = await refund().set('X-CSRF-Token', ASHA.csrfToken).set('Sec-Fetch-Site', 'same-origin');
    expect(res.status).toBe(201);
    expect(res.body).toMatchObject({ orderId: 101, amountMinor: 500 });
    expect(await refundCount()).toBe(1);
  });

  test("a refund on another merchant's order answers 404 and creates nothing", async () => {
    const res = await request(app)
      .post('/orders/201/refunds')
      .set('Cookie', asAsha)
      .set('X-CSRF-Token', ASHA.csrfToken)
      .send({ amountMinor: 500 });
    expect(res.status).toBe(404);
    expect(await refundCount()).toBe(0);
  });
});
