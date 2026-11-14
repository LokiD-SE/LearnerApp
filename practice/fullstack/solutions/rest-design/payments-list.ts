// Exercise: list the merchant's payments with cursor (keyset) pagination.
// Tests: tests/rest-design/payments-list.test.ts
//
//   GET /payments?limit=20&cursor=...
//   200 { "data": [...payments, newest first], "nextCursor": "..." }   + Link: <...>; rel="next"
//
// Rules:
// - Order: newest createdAt first; payments with the same createdAt by id, descending. A stable,
//   unique sort order is what makes a cursor possible.
// - limit: an integer from 1 upwards, default 20; values above 100 are treated as 100.
//   Anything else (0, -1, 2.5, abc) is a 400 invalid-parameter problem.
// - cursor: opaque to clients. It marks the last item of the previous page, so a page continues
//   strictly after it - payments created meanwhile never shift the pages a client is walking.
//   A cursor the server can't decode is a 400 invalid-cursor problem.
// - Last page: no nextCursor member at all (not null) and no Link header.
import express, { type Express } from 'express';
import { PROBLEMS, sendProblem } from './problem.js';
import type { Payment, SandPayStore } from './sandpay-store.js';

const DEFAULT_LIMIT = 20;
const MAX_LIMIT = 100;

interface Position {
  createdAt: string;
  id: string;
}

/** Newest first; ties broken by id, descending. Returns < 0 when a comes first. */
function compare(a: Position, b: Position): number {
  if (a.createdAt !== b.createdAt) return a.createdAt < b.createdAt ? 1 : -1;
  if (a.id !== b.id) return a.id < b.id ? 1 : -1;
  return 0;
}

export function encodeCursor(position: Position): string {
  return Buffer.from(JSON.stringify([position.createdAt, position.id])).toString('base64url');
}

export function decodeCursor(cursor: string): Position | undefined {
  try {
    const value: unknown = JSON.parse(Buffer.from(cursor, 'base64url').toString('utf8'));
    if (
      Array.isArray(value) &&
      value.length === 2 &&
      typeof value[0] === 'string' &&
      typeof value[1] === 'string'
    )
      return { createdAt: value[0], id: value[1] };
  } catch {
    // not base64url JSON - fall through
  }
  return undefined;
}

export function createPaymentsListApp(store: SandPayStore): Express {
  const app = express();

  app.get('/payments', (req, res) => {
    const rawLimit = req.query.limit;
    let limit = DEFAULT_LIMIT;
    if (rawLimit !== undefined) {
      const parsed = typeof rawLimit === 'string' && /^\d+$/.test(rawLimit) ? Number(rawLimit) : NaN;
      if (!Number.isSafeInteger(parsed) || parsed < 1)
        return sendProblem(res, {
          type: `${PROBLEMS}invalid-parameter`,
          title: 'Invalid query parameter',
          status: 400,
          detail: 'limit must be a positive integer.',
          parameter: 'limit',
        });
      limit = Math.min(parsed, MAX_LIMIT);
    }

    const rawCursor = req.query.cursor;
    let after: Position | undefined;
    if (rawCursor !== undefined) {
      after = typeof rawCursor === 'string' ? decodeCursor(rawCursor) : undefined;
      if (!after)
        return sendProblem(res, {
          type: `${PROBLEMS}invalid-cursor`,
          title: 'Invalid cursor',
          status: 400,
          detail: 'Use the nextCursor from a previous response, unchanged.',
          parameter: 'cursor',
        });
    }

    const sorted = [...store.payments].sort(compare);
    const start = after ? sorted.filter((payment) => compare(payment, after) > 0) : sorted;
    const page: Payment[] = start.slice(0, limit);
    const hasMore = start.length > limit;

    const body: { data: Payment[]; nextCursor?: string } = { data: page };
    const last = page.at(-1);
    if (hasMore && last) {
      body.nextCursor = encodeCursor(last);
      const next = new URLSearchParams({ limit: String(limit), cursor: body.nextCursor });
      res.set('Link', `</payments?${next.toString()}>; rel="next"`);
    }
    res.json(body);
  });

  return app;
}
