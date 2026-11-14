import * as z from 'zod';
import {
  CreateRefundBody,
  ListRefundsQuery,
  MAX_REFUND_MINOR,
  toFieldErrors,
} from '../../exercises/validation/refund-schema.js';

const valid = { amountMinor: 2599, currency: 'EUR', reason: 'duplicate' };

/** The field errors for an invalid input, or a failed assertion if it was accepted. */
function errorsFor(schema: z.ZodType, input: unknown) {
  const result = schema.safeParse(input);
  expect(result.success, `expected ${JSON.stringify(input)} to be rejected`).toBe(false);
  return toFieldErrors((result as { error: z.ZodError }).error);
}

function pointersFor(schema: z.ZodType, input: unknown): string[] {
  return errorsFor(schema, input).map((e) => e.pointer);
}

describe('CreateRefundBody', { tags: ['@exercise'] }, () => {
  test('accepts a valid refund and returns the typed data', () => {
    expect(CreateRefundBody.parse(valid)).toEqual(valid);
    expect(CreateRefundBody.parse({ ...valid, amountMinor: 1 })).toEqual({ ...valid, amountMinor: 1 });
    expect(CreateRefundBody.parse({ ...valid, amountMinor: MAX_REFUND_MINOR }).amountMinor).toBe(
      MAX_REFUND_MINOR,
    );
  });

  test.each([
    ['zero', 0],
    ['negative', -500],
    ['a fraction', 25.99],
    ['over the maximum', MAX_REFUND_MINOR + 1],
    ['a numeric string', '2599'],
    ['null', null],
    ['NaN-like string', 'NaN'],
  ])('rejects amountMinor %s', (_name, amountMinor) => {
    expect(pointersFor(CreateRefundBody, { ...valid, amountMinor })).toEqual(['#/amountMinor']);
  });

  test('uses an exact allow-list for currency', () => {
    for (const currency of ['GBP', 'INR', 'USD']) {
      expect(CreateRefundBody.safeParse({ ...valid, currency }).success).toBe(true);
    }
    for (const currency of ['eur', ' EUR', 'JPY', 'XXX', '', 978]) {
      expect(pointersFor(CreateRefundBody, { ...valid, currency })).toEqual(['#/currency']);
    }
  });

  test('accepts only the listed reasons', () => {
    expect(pointersFor(CreateRefundBody, { ...valid, reason: 'because' })).toEqual(['#/reason']);
    expect(pointersFor(CreateRefundBody, { amountMinor: 2599, currency: 'EUR' })).toEqual(['#/reason']);
  });

  test('rejects unknown keys instead of dropping them silently', () => {
    const errors = errorsFor(CreateRefundBody, { ...valid, isApproved: true });
    expect(errors).toHaveLength(1);
    expect(errors[0]!.pointer).toBe('#');
    expect(errors[0]!.detail).toContain('isApproved');
  });

  test('trims the note and limits it to 500 characters', () => {
    expect(CreateRefundBody.parse({ ...valid, note: '  customer called  ' }).note).toBe('customer called');
    expect(CreateRefundBody.parse({ ...valid, note: 'x'.repeat(500) }).note).toHaveLength(500);
    expect(pointersFor(CreateRefundBody, { ...valid, note: 'x'.repeat(501) })).toEqual(['#/note']);
    expect(pointersFor(CreateRefundBody, { ...valid, note: '   ' })).toEqual(['#/note']);
  });

  test('requires a note when the reason is "other"', () => {
    expect(errorsFor(CreateRefundBody, { ...valid, reason: 'other' })).toEqual([
      { pointer: '#/note', detail: 'note is required when reason is other' },
    ]);
    expect(CreateRefundBody.parse({ ...valid, reason: 'other', note: 'chargeback avoided' }).note).toBe(
      'chargeback avoided',
    );
  });
});

describe('ListRefundsQuery', { tags: ['@exercise'] }, () => {
  test('defaults limit to 20 and converts digits to a number', () => {
    expect(ListRefundsQuery.parse({})).toEqual({ limit: 20 });
    expect(ListRefundsQuery.parse({ limit: '1' })).toEqual({ limit: 1 });
    expect(ListRefundsQuery.parse({ limit: '100', status: 'failed' })).toEqual({
      limit: 100,
      status: 'failed',
    });
  });

  test.each(['', ' 20', '2e1', '20.0', '0x10', '0', '101', 'abc'])('rejects limit=%j', (limit) => {
    expect(pointersFor(ListRefundsQuery, { limit })).toEqual(['#/limit']);
  });

  test('rejects a repeated limit parameter', () => {
    expect(pointersFor(ListRefundsQuery, { limit: ['10', '20'] })).toEqual(['#/limit']);
  });

  test('checks status and ignores unknown parameters', () => {
    expect(pointersFor(ListRefundsQuery, { status: 'SUCCEEDED' })).toEqual(['#/status']);
    expect(ListRefundsQuery.parse({ utm_source: 'mail' })).toEqual({ limit: 20 });
  });
});

describe('toFieldErrors', { tags: ['@exercise'] }, () => {
  test('writes each issue path as a JSON Pointer fragment', () => {
    const error = new z.ZodError([
      { code: 'custom', path: ['items', 0, 'sku'], message: 'unknown sku', input: 'x' },
      { code: 'custom', path: [], message: 'whole body', input: {} },
      { code: 'custom', path: ['a/b', 'c~d'], message: 'escaped', input: 1 },
    ]);
    expect(toFieldErrors(error)).toEqual([
      { pointer: '#/items/0/sku', detail: 'unknown sku' },
      { pointer: '#', detail: 'whole body' },
      { pointer: '#/a~1b/c~0d', detail: 'escaped' },
    ]);
  });
});
