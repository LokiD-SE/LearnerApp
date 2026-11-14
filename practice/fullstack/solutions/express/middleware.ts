// Exercise: the cross-cutting middleware every route of the SandPay API (fictional) relies on -
// a request id for tracing, a JSON 404 for unknown routes, and an error handler that never leaks
// internals. Tests: tests/express/middleware.test.ts

import { randomUUID } from 'node:crypto';
import type { ErrorRequestHandler, RequestHandler } from 'express';

/** Ids a client may send in X-Request-Id: 1-64 letters, digits or hyphens. Anything else is replaced. */
const SAFE_ID = /^[A-Za-z0-9-]{1,64}$/;

/**
 * Gives every request an id. Reuse the incoming `X-Request-Id` header when it is safe (see SAFE_ID);
 * otherwise generate one with `randomUUID()`. Store it in `res.locals.requestId` for later middleware
 * and send it back in the `X-Request-Id` response header - on EVERY response, errors included.
 */
export function requestId(): RequestHandler {
  return (req, res, next) => {
    const incoming = req.get('X-Request-Id');
    const id = incoming !== undefined && SAFE_ID.test(incoming) ? incoming : randomUUID();
    res.locals.requestId = id;
    res.set('X-Request-Id', id);
    next();
  };
}

/**
 * The last ordinary middleware: nothing matched, so answer 404 with JSON
 * `{ "error": "not_found", "requestId": "..." }` instead of Express's HTML "Cannot GET /x".
 */
export const notFound: RequestHandler = (req, res) => {
  res.status(404).json({ error: 'not_found', requestId: res.locals.requestId });
};

/**
 * The error handler - it must take four arguments, or Express treats it as ordinary middleware.
 *
 * - If the response has already started (`res.headersSent`), hand the error to Express: `next(err)`.
 * - Malformed JSON from express.json() (`err.type === 'entity.parse.failed'`) -> 400 `malformed_json`.
 * - A body over the size limit (`err.type === 'entity.too.large'`) -> 413 `payload_too_large`.
 * - Anything else -> 500 `internal_error`. Log the error on the server (`console.error`), but never
 *   send its message or stack to the client.
 *
 * Every body is `{ "error": "<code>", "requestId": "..." }`.
 */
export const errorHandler: ErrorRequestHandler = (err, req, res, next) => {
  if (res.headersSent) {
    next(err);
    return;
  }
  const type = typeof err === 'object' && err !== null ? (err as { type?: unknown }).type : undefined;
  let status = 500;
  let code = 'internal_error';
  if (type === 'entity.parse.failed') {
    status = 400;
    code = 'malformed_json';
  } else if (type === 'entity.too.large') {
    status = 413;
    code = 'payload_too_large';
  } else {
    console.error(`[${String(res.locals.requestId)}]`, err);
  }
  res.status(status).json({ error: code, requestId: res.locals.requestId });
};
