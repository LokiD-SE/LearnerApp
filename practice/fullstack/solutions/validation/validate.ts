// Exercise: validation middleware and one central error handler that turns every error into
// Problem Details (RFC 9457) without leaking internals. Do refund-schema.ts first - this file
// uses its toFieldErrors(). Tests: tests/validation/validate.test.ts
import type { ErrorRequestHandler, RequestHandler } from 'express';
import type * as z from 'zod';
import { type FieldError, toFieldErrors } from './refund-schema.js';

/** Base URI of SandPay's problem types (fictional). A type is a stable identifier, not a page. */
export const PROBLEMS = 'https://api.sandpay.example/problems/';

/** The request failed its schema. Carries the field errors for the 422 response. */
export class ValidationError extends Error {
  constructor(readonly errors: FieldError[]) {
    super('request validation failed');
    this.name = 'ValidationError';
  }
}

/**
 * An expected, operational failure the client can act on - payment not found, refund exceeds the
 * captured amount... Its title and detail are written for the client and are safe to send.
 */
export class AppError extends Error {
  constructor(
    readonly status: number,
    readonly slug: string,
    readonly title: string,
    readonly detail?: string,
  ) {
    super(title);
    this.name = 'AppError';
  }
}

/**
 * Validates `req.body` against `schema`.
 *
 * - The request must be JSON (`req.is('application/json')`); otherwise pass
 *   `new AppError(415, 'unsupported-media-type', 'Content-Type must be application/json')` to next().
 * - On success, REPLACE `req.body` with the parsed data (trimmed, defaults applied, unknown keys
 *   handled by the schema) and call next().
 * - On failure, call next(new ValidationError(toFieldErrors(error))). Never throw from here and
 *   never send the response here - the error handler owns the response format.
 */
export function validateBody(schema: z.ZodType): RequestHandler {
  return (req, res, next) => {
    if (!req.is('application/json')) {
      next(new AppError(415, 'unsupported-media-type', 'Content-Type must be application/json'));
      return;
    }
    const result = schema.safeParse(req.body);
    if (!result.success) {
      next(new ValidationError(toFieldErrors(result.error)));
      return;
    }
    req.body = result.data;
    next();
  };
}

/**
 * Validates `req.query` against `schema`. Express 5 makes `req.query` a read-only getter, so put the
 * parsed result in `res.locals.query` instead. Failures go to next() as a ValidationError, like
 * validateBody.
 */
export function validateQuery(schema: z.ZodType): RequestHandler {
  return (req, res, next) => {
    const result = schema.safeParse(req.query);
    if (!result.success) {
      next(new ValidationError(toFieldErrors(result.error)));
      return;
    }
    res.locals.query = result.data;
    next();
  };
}

/**
 * The last middleware of the app. Every response it sends is `application/problem+json` with
 * `type` (PROBLEMS + slug), `title`, `status` and the extension `requestId` (from res.locals.requestId):
 *
 * | error                                      | status | slug                  | extra members        |
 * |--------------------------------------------|--------|-----------------------|----------------------|
 * | ValidationError                            | 422    | validation-error      | `errors` (FieldError[]), title "Your request is not valid." |
 * | express.json() `entity.parse.failed`       | 400    | malformed-json        | title "Request body is not valid JSON" |
 * | express.json() `entity.too.large`          | 413    | payload-too-large     | title "Request body is too large" |
 * | AppError                                   | its    | its slug              | its title, and `detail` if set |
 * | anything else (a bug, a database outage)   | 500    | internal-error        | title "Internal Server Error" ONLY |
 *
 * For the 500: log the real error on the server with the request id (`console.error`), and send
 * nothing from it - no message, no stack, no SQL. If the response has already started
 * (`res.headersSent`), call next(err) instead.
 */
export const problemHandler: ErrorRequestHandler = (err, req, res, next) => {
  if (res.headersSent) {
    next(err);
    return;
  }
  const requestId = res.locals.requestId as string | undefined;
  const send = (status: number, slug: string, title: string, extra: Record<string, unknown> = {}) => {
    res
      .status(status)
      .type('application/problem+json')
      .json({ type: PROBLEMS + slug, title, status, ...extra, requestId });
  };
  const bodyParserType =
    typeof err === 'object' && err !== null ? (err as { type?: unknown }).type : undefined;

  if (err instanceof ValidationError) {
    send(422, 'validation-error', 'Your request is not valid.', { errors: err.errors });
  } else if (bodyParserType === 'entity.parse.failed') {
    send(400, 'malformed-json', 'Request body is not valid JSON');
  } else if (bodyParserType === 'entity.too.large') {
    send(413, 'payload-too-large', 'Request body is too large');
  } else if (err instanceof AppError) {
    send(err.status, err.slug, err.title, err.detail === undefined ? {} : { detail: err.detail });
  } else {
    console.error(`[${requestId ?? 'no-request-id'}] unexpected error`, err);
    send(500, 'internal-error', 'Internal Server Error');
  }
};
