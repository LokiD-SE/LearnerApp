// Reference solution: the SandPay merchant dashboard API. See the exercise file for the contract.
import cookieParser from 'cookie-parser';
import express, { type ErrorRequestHandler, type Express, type Request, type Response } from 'express';
import * as z from 'zod';
import type { PGlite } from '@electric-sql/pglite';
import { createRefund, PROBLEMS } from './refund-service.js';

export interface DashboardApiOptions {
  db: PGlite;
  /** Session id (the `sid` cookie) to the signed-in merchant's id. */
  sessions: Map<string, number>;
}

export interface PaymentRow {
  id: string;
  amountMinor: number;
  currency: string;
  refundedMinor: number;
  refundableMinor: number;
  createdAt: string;
}

const RefundBody = z.strictObject({ amountMinor: z.number().int().min(1).max(10_000_000) });
const KEY = /^[A-Za-z0-9_-]{8,255}$/;

export function sendProblem(
  res: Response,
  status: number,
  name: string,
  title: string,
  extra: Record<string, unknown> = {},
): void {
  res
    .status(status)
    .type('application/problem+json')
    .json({ type: `${PROBLEMS}${name}`, title, status, ...extra });
}

/** The key from `Idempotency-Key: "abc"` (a Structured Field String) or a bare `abc`. */
export function idempotencyKeyOf(req: Request): string | undefined {
  const raw = req.get('Idempotency-Key')?.trim();
  if (raw === undefined || raw === '') return undefined;
  return raw.length >= 2 && raw.startsWith('"') && raw.endsWith('"') ? raw.slice(1, -1) : raw;
}

export function createDashboardApi({ db, sessions }: DashboardApiOptions): Express {
  const app = express();
  app.disable('x-powered-by');
  app.use(cookieParser());
  app.use(express.json());

  // Liveness and readiness in one small check: can we reach the database? No session needed.
  app.get('/healthz', async (_req, res) => {
    try {
      await db.query('SELECT 1');
      res.json({ status: 'ok' });
    } catch {
      res.status(503).json({ status: 'unavailable' });
    }
  });

  // Deny by default: everything under /api needs a session.
  app.use('/api', (req, res, next) => {
    const merchantId = sessions.get(String(req.cookies.sid));
    if (merchantId === undefined) return void sendProblem(res, 401, 'sign-in-required', 'Sign in required');
    res.locals.merchantId = merchantId;
    next();
  });

  app.get('/api/payments', async (_req, res) => {
    const result = await db.query<PaymentRow>(
      `SELECT id, amount_minor::integer AS "amountMinor", currency, refunded_minor::integer AS "refundedMinor",
              (amount_minor - refunded_minor)::integer AS "refundableMinor",
              to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS "createdAt"
         FROM payments WHERE merchant_id = $1 ORDER BY created_at DESC, id`,
      [res.locals.merchantId],
    );
    res.json({ payments: result.rows });
  });

  app.post('/api/payments/:paymentId/refunds', async (req, res) => {
    const key = idempotencyKeyOf(req);
    if (key === undefined) {
      return void sendProblem(res, 400, 'idempotency-key-missing', 'Idempotency-Key header is required');
    }
    if (!KEY.test(key)) {
      return void sendProblem(res, 400, 'idempotency-key-invalid', 'Idempotency-Key is not a valid key', {
        detail: 'Use 8 to 255 letters, digits, "-" or "_" - a UUID is recommended.',
      });
    }
    if (!req.is('application/json')) {
      return void sendProblem(res, 415, 'unsupported-media-type', 'Content-Type must be application/json');
    }
    const parsed = RefundBody.safeParse(req.body);
    if (!parsed.success) {
      return void sendProblem(res, 422, 'validation-error', 'The request is not valid', {
        errors: parsed.error.issues.map((issue) => ({
          detail: issue.message,
          pointer: `#/${issue.path.join('/')}`,
        })),
      });
    }

    const outcome = await createRefund(db, {
      merchantId: res.locals.merchantId as number,
      paymentId: String(req.params.paymentId),
      amountMinor: parsed.data.amountMinor,
      idempotencyKey: key,
    });
    if (outcome.replayed) res.set('Idempotent-Replayed', 'true');
    if (outcome.status === 201) {
      res.set(
        'Location',
        `/api/payments/${String(req.params.paymentId)}/refunds/${String(outcome.body.refundId)}`,
      );
    }
    res.status(outcome.status);
    if (outcome.status >= 400) res.type('application/problem+json');
    res.json(outcome.body);
  });

  // Last: every error becomes a problem. Express 5 sends rejected promises from async handlers here.
  const onError: ErrorRequestHandler = (err: unknown, _req, res, _next) => {
    const status = (err as { status?: unknown }).status;
    if (status === 400 && (err as { type?: unknown }).type === 'entity.parse.failed') {
      return void sendProblem(res, 400, 'malformed-json', 'The body is not valid JSON');
    }
    // Log the details on the server; send none of them to the client.
    console.error(err);
    sendProblem(res, 500, 'internal-error', 'Something went wrong');
  };
  app.use(onError);

  return app;
}
