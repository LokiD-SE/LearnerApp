// The SandPay merchant API - reference solution. Same routes and response shapes as the exercise, with the
// six fixes: deny-by-default access control, a parameterised search, HTML-encoded output, security headers,
// an allow-listed CORS policy and CSRF protection (synchronizer token + Fetch Metadata).
import { timingSafeEqual } from 'node:crypto';
import cookieParser from 'cookie-parser';
import express, { type Express, type NextFunction, type Request, type Response } from 'express';
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

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

/** Encodes the five characters that matter in HTML text and quoted attribute values. */
export function escapeHtml(text: string): string {
  return text
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#x27;');
}

/** Compares two strings in time that doesn't depend on where they differ. */
function sameSecret(a: string, b: string): boolean {
  const left = Buffer.from(a);
  const right = Buffer.from(b);
  return left.length === right.length && timingSafeEqual(left, right);
}

export function createMerchantApi({ db, sessions, allowedOrigins }: MerchantApiOptions): Express {
  const app = express();
  app.disable('x-powered-by');
  app.use(cookieParser());
  app.use(express.json());

  // Security headers on every response. This API serves JSON and one plain HTML page with no scripts,
  // styles or images, so the policy can allow nothing at all.
  app.use((_req, res, next) => {
    res.set('X-Content-Type-Options', 'nosniff');
    res.set(
      'Content-Security-Policy',
      "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
    );
    res.set('Referrer-Policy', 'strict-origin-when-cross-origin');
    next();
  });

  // CORS: only the dashboard origins may read responses, and only they may send credentials.
  const allowed = new Set(allowedOrigins);
  app.use((req, res, next) => {
    res.vary('Origin');
    const origin = req.get('Origin');
    if (origin && allowed.has(origin)) {
      res.set('Access-Control-Allow-Origin', origin);
      res.set('Access-Control-Allow-Credentials', 'true');
      if (req.method === 'OPTIONS') {
        res.set('Access-Control-Allow-Methods', 'GET, POST');
        res.set('Access-Control-Allow-Headers', 'Content-Type, X-CSRF-Token');
        return void res.sendStatus(204);
      }
    }
    next();
  });

  // The public page comes before the sign-in check.
  app.get('/receipt', (req, res) => {
    const ref = escapeHtml(String(req.query.ref ?? ''));
    res
      .status(404)
      .type('html')
      .send(`<!doctype html><title>Receipt</title><h1>Receipt ${ref} not found</h1>`);
  });

  // Deny by default: everything after this needs a session.
  app.use((req: Request, res: Response, next: NextFunction) => {
    const session = sessions.get(String(req.cookies.sid));
    if (!session) return void res.status(401).json({ error: 'sign_in_required' });
    res.locals.session = session;
    next();
  });

  // CSRF: state-changing requests need the session's token, and cross-site ones are refused outright.
  app.use((req, res, next) => {
    if (SAFE_METHODS.has(req.method)) return next();
    const session = res.locals.session as Session;
    const token = req.get('X-CSRF-Token') ?? '';
    if (req.get('Sec-Fetch-Site') === 'cross-site' || !sameSecret(token, session.csrfToken)) {
      return void res.status(403).json({ error: 'csrf_check_failed' });
    }
    next();
  });

  /** The order, if it exists and belongs to the signed-in merchant - otherwise undefined (answer 404). */
  async function ownOrder(res: Response, id: string): Promise<Order | undefined> {
    const session = res.locals.session as Session;
    const result = await db.query<Order>(
      `SELECT ${ORDER_COLUMNS} FROM orders WHERE id = $1 AND merchant_id = $2`,
      [Number(id), session.merchantId],
    );
    return result.rows[0];
  }

  app.get('/orders', async (req, res) => {
    const session = res.locals.session as Session;
    const q = String(req.query.q ?? '');
    const result = await db.query<Order>(
      `SELECT ${ORDER_COLUMNS} FROM orders
       WHERE merchant_id = $1 AND customer_email ILIKE '%' || $2 || '%' ORDER BY id`,
      [session.merchantId, q],
    );
    res.json({ orders: result.rows });
  });

  app.get('/orders/:id', async (req, res) => {
    const order = await ownOrder(res, req.params.id);
    if (!order) return void res.status(404).json({ error: 'order_not_found' });
    res.json(order);
  });

  app.post('/orders/:id/refunds', async (req, res) => {
    const order = await ownOrder(res, req.params.id);
    if (!order) return void res.status(404).json({ error: 'order_not_found' });
    const amountMinor: unknown = req.body?.amountMinor;
    if (
      typeof amountMinor !== 'number' ||
      !Number.isInteger(amountMinor) ||
      amountMinor < 1 ||
      amountMinor > order.amountMinor
    ) {
      return void res.status(422).json({ error: 'invalid_amount' });
    }
    const refund = await db.query<{ id: number }>(
      'INSERT INTO refunds (order_id, amount_minor) VALUES ($1, $2) RETURNING id',
      [order.id, amountMinor],
    );
    res.status(201).json({ refundId: refund.rows[0]?.id, orderId: order.id, amountMinor });
  });

  return app;
}
