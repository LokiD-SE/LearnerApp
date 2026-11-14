// The SandPay merchant API - a deliberately vulnerable first draft. It works for a merchant who uses it
// honestly, and every test in tests/owasp/merchant-api.test.ts that plays the attacker fails.
//
// Fix it without changing the routes or the response shapes:
//   1. Access control - only a signed-in merchant reaches /orders, and only their own orders (deny by default).
//   2. Injection - the order search must not be built by gluing user input into SQL.
//   3. XSS - the receipt page must not reflect the reference as HTML.
//   4. Headers - no X-Powered-By; nosniff and a Content-Security-Policy on every response.
//   5. CORS - only the dashboard origins in `allowedOrigins` may read responses with credentials.
//   6. CSRF - a refund (POST) needs the session's CSRF token in X-CSRF-Token, and a cross-site request
//      (Sec-Fetch-Site: cross-site) is refused even with a token.
import cookieParser from 'cookie-parser';
import express, { type Express, type Request } from 'express';
import type { PGlite } from '@electric-sql/pglite';
import { ORDER_COLUMNS, type Order } from './sandpay-db.js';

export interface Session {
  merchantId: number;
  /** A random value created at sign-in; the dashboard sends it back in X-CSRF-Token. */
  csrfToken: string;
}

export interface MerchantApiOptions {
  db: PGlite;
  /** Session id (the `sid` cookie) to session. */
  sessions: Map<string, Session>;
  /** Origins of the merchant dashboard, for example https://dashboard.sandpay.example. */
  allowedOrigins: string[];
}

export function createMerchantApi({ db, sessions }: MerchantApiOptions): Express {
  const app = express();
  app.use(cookieParser());
  app.use(express.json());

  // "CORS so the dashboard works": echoes whatever Origin asks.
  app.use((req, res, next) => {
    const origin = req.get('Origin');
    if (origin) {
      res.set('Access-Control-Allow-Origin', origin);
      res.set('Access-Control-Allow-Credentials', 'true');
    }
    next();
  });

  const sessionOf = (req: Request): Session | undefined => sessions.get(String(req.cookies.sid));

  app.get('/orders', async (req, res) => {
    const session = sessionOf(req);
    if (!session) return void res.status(401).json({ error: 'sign_in_required' });
    const q = String(req.query.q ?? '');
    const result = await db.query<Order>(
      `SELECT ${ORDER_COLUMNS} FROM orders
       WHERE merchant_id = ${session.merchantId} AND customer_email ILIKE '%${q}%' ORDER BY id`,
    );
    res.json({ orders: result.rows });
  });

  app.get('/orders/:id', async (req, res) => {
    const session = sessionOf(req);
    if (!session) return void res.status(401).json({ error: 'sign_in_required' });
    const result = await db.query<Order>(`SELECT ${ORDER_COLUMNS} FROM orders WHERE id = $1`, [
      Number(req.params.id),
    ]);
    if (!result.rows[0]) return void res.status(404).json({ error: 'order_not_found' });
    res.json(result.rows[0]);
  });

  app.post('/orders/:id/refunds', async (req, res) => {
    const session = sessionOf(req);
    if (!session) return void res.status(401).json({ error: 'sign_in_required' });
    const order = await db.query<Order>(`SELECT ${ORDER_COLUMNS} FROM orders WHERE id = $1`, [
      Number(req.params.id),
    ]);
    if (!order.rows[0]) return void res.status(404).json({ error: 'order_not_found' });
    const amountMinor: unknown = req.body?.amountMinor;
    if (
      typeof amountMinor !== 'number' ||
      !Number.isInteger(amountMinor) ||
      amountMinor < 1 ||
      amountMinor > order.rows[0].amountMinor
    ) {
      return void res.status(422).json({ error: 'invalid_amount' });
    }
    const refund = await db.query<{ id: number }>(
      'INSERT INTO refunds (order_id, amount_minor) VALUES ($1, $2) RETURNING id',
      [order.rows[0].id, amountMinor],
    );
    res.status(201).json({ refundId: refund.rows[0]?.id, orderId: order.rows[0].id, amountMinor });
  });

  // A public page: the customer's e-mail links here with ?ref=<receipt reference>.
  app.get('/receipt', (req, res) => {
    const ref = String(req.query.ref ?? '');
    res
      .status(404)
      .type('html')
      .send(`<!doctype html><title>Receipt</title><h1>Receipt ${ref} not found</h1>`);
  });

  return app;
}
