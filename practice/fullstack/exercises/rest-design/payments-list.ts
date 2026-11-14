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
//   Anything else (0, -1, 2.5, abc, empty) is a 400 invalid-parameter problem.
// - cursor: opaque to clients and URL-safe. It marks the last item of the previous page, so a page
//   continues strictly after it - payments created meanwhile never shift the pages a client is walking.
//   A cursor the server can't decode is a 400 invalid-cursor problem.
// - When there is a next page: `nextCursor` in the body and a Link header (RFC 8288)
//   `</payments?limit=<limit>&cursor=<nextCursor>>; rel="next"`.
// - Last page: no nextCursor member at all (not null) and no Link header.
//
// Errors go through sendProblem (problem.ts) with type `${PROBLEMS}<name>`, a title and status 400.
import express, { type Express } from 'express';
import type { SandPayStore } from './sandpay-store.js';

export function createPaymentsListApp(store: SandPayStore): Express {
  const app = express();

  app.get('/payments', (_req, _res) => {
    // TODO: read limit and cursor from req.query, sort a copy of store.payments, take the page
    // after the cursor, and answer with data, nextCursor and the Link header.
    throw new Error(`TODO: list ${store.payments.length} payments`);
  });

  return app;
}
