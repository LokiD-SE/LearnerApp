import { groupBy, parseRefundRequest } from '../../exercises/ts/refund-requests.js';

describe('parseRefundRequest', { tags: ['@exercise'] }, () => {
  test('accepts a valid request and keeps only the known fields', () => {
    const result = parseRefundRequest(
      JSON.parse(
        '{"paymentId":"pay_1042","amountMinor":1250,"currency":"EUR","reason":"damaged","admin":true}',
      ),
    );
    expect(result).toEqual({
      ok: true,
      value: { paymentId: 'pay_1042', amountMinor: 1250, currency: 'EUR', reason: 'damaged' },
    });
  });

  test('reason is optional', () => {
    expect(parseRefundRequest({ paymentId: 'pay_1', amountMinor: 1, currency: 'INR' })).toEqual({
      ok: true,
      value: { paymentId: 'pay_1', amountMinor: 1, currency: 'INR' },
    });
  });

  test.each([null, 'pay_1', 42, undefined])('rejects a body that is not an object: %s', (input) => {
    expect(parseRefundRequest(input)).toEqual({ ok: false, error: ['body: must be an object'] });
  });

  test('reports every problem, each naming its field', () => {
    const result = parseRefundRequest({ paymentId: 1042, amountMinor: 12.5, currency: 'eur', reason: 7 });
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.error).toHaveLength(4);
    for (const field of ['paymentId', 'amountMinor', 'currency', 'reason'])
      expect(result.error.some((message) => message.startsWith(`${field}:`))).toBe(true);
  });

  test.each([
    ['a decimal amount', { amountMinor: 12.5 }, 'amountMinor'],
    ['a zero amount', { amountMinor: 0 }, 'amountMinor'],
    ['an amount sent as a string', { amountMinor: '1250' }, 'amountMinor'],
    ['an unsafe integer', { amountMinor: 2 ** 53 }, 'amountMinor'],
    ['an id without the pay_ prefix', { paymentId: 'ord_1042' }, 'paymentId'],
    ['an unknown currency', { currency: 'JPY' }, 'currency'],
    ['a reason that is too long', { reason: 'x'.repeat(201) }, 'reason'],
  ])('rejects %s', (_name, change, field) => {
    const result = parseRefundRequest({ paymentId: 'pay_1', amountMinor: 100, currency: 'GBP', ...change });
    expect(result).toEqual({ ok: false, error: [expect.stringMatching(new RegExp(`^${field}:`))] });
  });
});

describe('groupBy', { tags: ['@exercise'] }, () => {
  const payments = [
    { id: 'pay_1', status: 'captured' },
    { id: 'pay_2', status: 'failed' },
    { id: 'pay_3', status: 'captured' },
  ] as const;

  test('groups by the key, keeping input order', () => {
    expect(groupBy(payments, (p) => p.status)).toEqual({
      captured: [payments[0], payments[2]],
      failed: [payments[1]],
    });
  });

  test('keys no item has are absent, and an empty list gives an empty object', () => {
    const groups = groupBy(payments, (p) => p.status);
    expect(Object.keys(groups)).toEqual(['captured', 'failed']);
    expect(groupBy([], (p: { id: string }) => p.id)).toEqual({});
  });
});
