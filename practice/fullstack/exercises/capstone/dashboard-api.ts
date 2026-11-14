// Capstone exercise 2: the SandPay merchant dashboard API (Express 5, PGlite, zod 4).
// Tests: tests/capstone/dashboard-api.test.ts. Do exercise 1 (refund-service.ts) first.
//
// The contract:
// - No X-Powered-By header. Every error body is Problem Details (RFC 9457), Content-Type
//   application/problem+json, type `${PROBLEMS}<name>` - use sendProblem below.
// - GET /healthz (no session): runs `SELECT 1`; 200 { status: 'ok' }, or 503 { status: 'unavailable' }
//   when the database fails. (Given - it already works.)
// - Everything under /api needs a session: the `sid` cookie must be a key of `sessions`, else
//   401 `sign-in-required`. Deny by default - one middleware, not a check in each route.
// - GET /api/payments -> 200 { payments: PaymentRow[] } - only the signed-in merchant's payments,
//   newest first; createdAt as an ISO 8601 UTC string such as "2026-11-12T14:02:00Z".
// - POST /api/payments/:paymentId/refunds, body { amountMinor }, in this order:
//   1. Idempotency-Key missing or empty -> 400 `idempotency-key-missing`. The value may be a
//      Structured Field String in double quotes ("..."), as the IETF draft writes it, or bare;
//      idempotencyKeyOf() below reads both.
//   2. a key that is not 8-255 of A-Z a-z 0-9 - _ -> 400 `idempotency-key-invalid`
//   3. Content-Type not JSON -> 415 `unsupported-media-type`
//   4. the body is not exactly { amountMinor: integer 1..10000000 } -> 422 `validation-error` with
//      `errors`: [{ detail, pointer }] where pointer is "#/amountMinor" (unknown keys are errors too)
//   5. otherwise call createRefund and send its status and body. A replayed answer carries the header
//      `Idempotent-Replayed: true` (SandPay's own header, not a standard). A 201 carries
//      Location: /api/payments/{paymentId}/refunds/{refundId}.
// - Malformed JSON -> 400 `malformed-json`. Anything unexpected -> 500 `internal-error` with no stack
//   trace or error message in the body (log it on the server instead).
import cookieParser from 'cookie-parser';
import express, { type Express, type Request, type Response } from 'express';
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
  app.use(cookieParser());
  app.use(express.json());

  app.get('/healthz', async (_req, res) => {
    try {
      await db.query('SELECT 1');
      res.json({ status: 'ok' });
    } catch {
      res.status(503).json({ status: 'unavailable' });
    }
  });

  // TODO: the session middleware for /api, GET /api/payments, POST /api/payments/:paymentId/refunds
  // (with a zod schema for the body) and an error-handling middleware (four parameters) at the end.
  void sessions;
  void z;
  void createRefund;

  return app;
}
