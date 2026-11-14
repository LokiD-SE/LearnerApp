// Exercise: the boundary schemas of SandPay's (fictional) create-refund endpoint, written with zod 4.
// Tests: tests/validation/refund-schema.test.ts
import * as z from 'zod';

/** The currencies SandPay settles in - an allow-list, not a pattern. */
export const CURRENCIES = ['EUR', 'GBP', 'INR', 'USD'] as const;
export const REASONS = ['duplicate', 'fraudulent', 'requested_by_customer', 'other'] as const;
/** The largest refund the API accepts in one request, in minor units (100000.00). */
export const MAX_REFUND_MINOR = 10_000_000;

/**
 * POST /payments/:id/refunds body.
 *
 * - `amountMinor`: an integer number of minor units (2599 is 25.99), at least 1 and at most
 *   MAX_REFUND_MINOR. A JSON string "2599" is NOT accepted - JSON bodies keep their types.
 * - `currency`: one of CURRENCIES, exactly (no lower case, no trimming).
 * - `reason`: one of REASONS.
 * - `note`: optional; trimmed; 1 to 500 characters after trimming. REQUIRED when `reason` is
 *   "other" - report that problem at the path ["note"] with the message "note is required when reason is other".
 * - Unknown keys (`status`, `isApproved`...) are rejected, not silently dropped.
 */
export const CreateRefundBody = z.object({
  // TODO: replace this loose first draft with the rules described above.
  amountMinor: z.number(),
  currency: z.string(),
  reason: z.string(),
  note: z.string().optional(),
});

export type CreateRefund = z.infer<typeof CreateRefundBody>;

/**
 * GET /payments/:id/refunds query string. Query values always arrive as strings, so:
 *
 * - `limit`: optional; a whole number from 1 to 100 written in digits only ("20"); defaults to 20.
 *   Reject "", " 20", "2e1", "20.0" and repeated parameters (?limit=1&limit=2 arrives as an array).
 * - `status`: optional; one of "pending", "succeeded", "failed".
 * - Unknown parameters are ignored (stripped) - query strings often carry tracking parameters.
 */
export const ListRefundsQuery = z.object({
  // TODO: z.coerce.number() looks right but accepts "", " 20", "2e1" and "0x10" - check the tests.
  limit: z.coerce.number().default(20),
  status: z.string().optional(),
});

export type ListRefunds = z.infer<typeof ListRefundsQuery>;

/** One entry of a validation problem's `errors` extension (RFC 9457 section 3, the 422 example). */
export interface FieldError {
  /** A JSON Pointer fragment to the field, for example "#/note" or "#/items/0/sku"; "#" for the whole body. */
  pointer: string;
  detail: string;
}

/**
 * Turns zod issues into RFC 9457-style field errors: one entry per issue, in zod's order, with the
 * issue's path as a JSON Pointer fragment (RFC 6901: "~" is written "~0" and "/" is written "~1").
 */
export function toFieldErrors(error: z.ZodError): FieldError[] {
  // TODO: a pointer is "#" followed by "/<segment>" for each path part, with ~ and / escaped.
  return error.issues.map((issue) => ({ pointer: issue.path.join('.'), detail: issue.message }));
}
