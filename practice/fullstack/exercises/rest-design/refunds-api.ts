// Exercise: design the SandPay refunds resource - a sub-resource of a payment - as an HTTP API.
// Tests: tests/rest-design/refunds-api.test.ts
//
//   POST  /payments/:paymentId/refunds             create a refund        -> 201 + Location + ETag
//   GET   /payments/:paymentId/refunds/:refundId   read it                -> 200 + ETag
//   PATCH /payments/:paymentId/refunds/:refundId   change its reason      -> 200 + new ETag
//
// The contract, rule by rule:
// - The refund's representation is the stored Refund without its internal `version` counter.
// - ETag: a strong entity tag that changes on every change, for example "v1", "v2" (with the quotes).
// - POST body: { amountMinor: positive integer, reason: string of 1-200 characters }.
//   * unknown payment                      -> 404 payment-not-found
//   * invalid fields                       -> 422 validation-error, with `errors`: one
//                                             { detail, pointer } per bad field ("#/amountMinor", "#/reason")
//   * amount above what is left to refund  -> 409 refund-exceeds-captured, with `refundableMinor`
//     (captured amount minus earlier refunds; a payment that isn't captured has 0 left)
//   * success -> 201, Location: /payments/{paymentId}/refunds/{refundId}, ETag, the representation.
// - GET: 200 + ETag; a refund id that doesn't exist, or belongs to another payment -> 404 refund-not-found.
// - PATCH takes JSON Merge Patch (RFC 7396). In this order (RFC 9110 section 13.2.1):
//   1. unknown refund                                 -> 404 refund-not-found
//   2. Content-Type is not application/merge-patch+json -> 415 unsupported-media-type,
//      with an Accept-Patch: application/merge-patch+json header
//   3. no If-Match                                    -> 428 precondition-required
//   4. If-Match matches neither the current ETag nor * -> 412 precondition-failed (strong comparison:
//      W/"v1" never matches; the header may hold a comma-separated list)
//   5. any field other than reason, or a bad reason   -> 422 validation-error
//   6. success -> 200, the new ETag and the representation.
// - Malformed JSON -> a 400 problem; anything unexpected -> a 500 problem. Never an HTML error page.
//
// Every error goes through sendProblem with type `${PROBLEMS}<name>`, a title and the status.
import express, { type Express } from 'express';
import type { Refund, SandPayStore } from './sandpay-store.js';

/** The refund as clients see it: everything except the internal version counter. */
export function toRepresentation(refund: Refund): Omit<Refund, 'version'> {
  throw new Error(`TODO: toRepresentation(${refund.id})`);
}

/** A strong entity tag (RFC 9110 section 8.8.3) that changes whenever the refund changes. */
export function etagOf(refund: Refund): string {
  throw new Error(`TODO: etagOf(${refund.id})`);
}

export function createRefundsApp(store: SandPayStore): Express {
  const app = express();
  // TODO: express.json() only parses application/json. PATCH bodies are application/merge-patch+json -
  // look at the `type` option of express.json.
  app.use(express.json());

  // TODO: the POST, GET and PATCH routes, using `store` (see sandpay-store.ts), and an error-handling
  // middleware (four parameters) at the end that answers with a problem.
  void store;

  return app;
}
