// Exercise: design the SandPay refunds resource - a sub-resource of a payment - as an HTTP API.
// Tests: tests/rest-design/refunds-api.test.ts
//
//   POST  /payments/:paymentId/refunds             create a refund        -> 201 + Location + ETag
//   GET   /payments/:paymentId/refunds/:refundId   read it                -> 200 + ETag
//   PATCH /payments/:paymentId/refunds/:refundId   change its reason      -> 200 + new ETag
//
// Every error is a Problem Details object (problem.ts). Problem types used:
//   payment-not-found, refund-not-found (404), validation-error (422), refund-exceeds-captured (409),
//   unsupported-media-type (415), precondition-required (428), precondition-failed (412).
import express, { type Express, type NextFunction, type Request, type Response } from 'express';
import { PROBLEMS, sendProblem } from './problem.js';
import type { Refund, SandPayStore } from './sandpay-store.js';

type FieldError = { detail: string; pointer: string };

/** The refund as clients see it: everything except the internal version counter. */
export function toRepresentation(refund: Refund) {
  const { version: _version, ...representation } = refund;
  return representation;
}

/** A strong entity tag (RFC 9110 section 8.8.3) that changes whenever the refund changes. */
export function etagOf(refund: Refund): string {
  return `"v${refund.version}"`;
}

function locationOf(refund: Refund): string {
  return `/payments/${refund.paymentId}/refunds/${refund.id}`;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function checkReason(value: unknown, errors: FieldError[]): void {
  if (typeof value !== 'string' || value.trim().length === 0 || value.length > 200)
    errors.push({ detail: 'must be a string of 1 to 200 characters', pointer: '#/reason' });
}

function validationProblem(res: Response, errors: FieldError[]): void {
  sendProblem(res, {
    type: `${PROBLEMS}validation-error`,
    title: 'Your request is not valid.',
    status: 422,
    errors,
  });
}

export function createRefundsApp(store: SandPayStore): Express {
  const app = express();
  // Express adds a weak ETag computed from the body to every response by default - error responses
  // included. This API sets its own ETags on refunds, so turn the automatic ones off.
  app.set('etag', false);
  // Parse both JSON and JSON Merge Patch (RFC 7396) bodies.
  app.use(express.json({ type: ['application/json', 'application/merge-patch+json'] }));

  app.post('/payments/:paymentId/refunds', (req, res) => {
    const payment = store.findPayment(req.params.paymentId);
    if (!payment)
      return sendProblem(res, {
        type: `${PROBLEMS}payment-not-found`,
        title: 'Payment not found',
        status: 404,
        detail: `There is no payment ${req.params.paymentId}.`,
      });

    const body: unknown = req.body;
    const errors: FieldError[] = [];
    const amount = isObject(body) ? body.amountMinor : undefined;
    if (!Number.isSafeInteger(amount) || (amount as number) <= 0)
      errors.push({ detail: 'must be a positive integer (minor units)', pointer: '#/amountMinor' });
    checkReason(isObject(body) ? body.reason : undefined, errors);
    if (errors.length > 0 || !isObject(body)) return validationProblem(res, errors);

    const amountMinor = body.amountMinor as number;
    const refunded = store.refundsFor(payment.id).reduce((sum, refund) => sum + refund.amountMinor, 0);
    const refundableMinor = payment.status === 'captured' ? payment.amountMinor - refunded : 0;
    if (amountMinor > refundableMinor)
      return sendProblem(res, {
        type: `${PROBLEMS}refund-exceeds-captured`,
        title: 'Refund exceeds the refundable amount',
        status: 409,
        detail: `Payment ${payment.id} has ${refundableMinor} minor units left to refund.`,
        refundableMinor,
      });

    const refund = store.addRefund({
      paymentId: payment.id,
      amountMinor,
      currency: payment.currency,
      reason: body.reason as string,
    });
    res.status(201).location(locationOf(refund)).set('ETag', etagOf(refund)).json(toRepresentation(refund));
  });

  /** The refund named by the URL, or undefined after sending a 404. */
  function findRefund(req: Request, res: Response): Refund | undefined {
    const refund = store.refunds.get(String(req.params.refundId));
    if (refund && refund.paymentId === req.params.paymentId) return refund;
    sendProblem(res, {
      type: `${PROBLEMS}refund-not-found`,
      title: 'Refund not found',
      status: 404,
      detail: `Payment ${String(req.params.paymentId)} has no refund ${String(req.params.refundId)}.`,
    });
    return undefined;
  }

  app.get('/payments/:paymentId/refunds/:refundId', (req, res) => {
    const refund = findRefund(req, res);
    if (!refund) return;
    res.set('ETag', etagOf(refund)).json(toRepresentation(refund));
  });

  app.patch('/payments/:paymentId/refunds/:refundId', (req, res) => {
    // Checks that need no request content come first (RFC 9110 section 13.2.1): 404, then 415,
    // then the preconditions, and only then the content itself.
    const refund = findRefund(req, res);
    if (!refund) return;

    if (!req.is('application/merge-patch+json')) {
      res.set('Accept-Patch', 'application/merge-patch+json');
      return sendProblem(res, {
        type: `${PROBLEMS}unsupported-media-type`,
        title: 'Unsupported Media Type',
        status: 415,
        detail: 'Send the changes as application/merge-patch+json.',
      });
    }

    const ifMatch = req.get('If-Match');
    if (ifMatch === undefined)
      return sendProblem(res, {
        type: `${PROBLEMS}precondition-required`,
        title: 'Precondition Required',
        status: 428,
        detail: 'Send If-Match with the ETag from your last GET, so you cannot overwrite a newer change.',
      });
    const current = etagOf(refund);
    const tags = ifMatch.split(',').map((tag) => tag.trim());
    // Strong comparison: a weak tag (W/"...") never matches for If-Match.
    if (!tags.includes('*') && !tags.includes(current))
      return sendProblem(res, {
        type: `${PROBLEMS}precondition-failed`,
        title: 'Precondition Failed',
        status: 412,
        detail: 'The refund has changed since you read it. GET it again and reapply your change.',
      });

    const body: unknown = req.body;
    const errors: FieldError[] = [];
    if (!isObject(body)) errors.push({ detail: 'must be a JSON object', pointer: '' });
    else {
      for (const field of Object.keys(body))
        if (field !== 'reason') errors.push({ detail: 'cannot be changed', pointer: `#/${field}` });
      if ('reason' in body) checkReason(body.reason, errors);
    }
    if (errors.length > 0 || !isObject(body)) return validationProblem(res, errors);

    const updated =
      'reason' in body ? store.updateRefund(refund.id, { reason: body.reason as string }) : refund;
    res.set('ETag', etagOf(updated)).json(toRepresentation(updated));
  });

  // Malformed JSON and anything unexpected also answer with Problem Details.
  app.use((error: unknown, _req: Request, res: Response, _next: NextFunction) => {
    const status =
      isObject(error) && typeof error.status === 'number' && error.status >= 400 && error.status < 500
        ? error.status
        : 500;
    sendProblem(res, {
      title: status === 500 ? 'Internal Server Error' : 'Bad Request',
      status,
      detail: status === 500 ? 'Something went wrong on our side.' : 'The request body is not valid JSON.',
    });
  });

  return app;
}
