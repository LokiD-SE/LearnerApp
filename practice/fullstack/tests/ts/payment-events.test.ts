import {
  applyEvent,
  describeEvent,
  type PaymentEvent,
  type PaymentView,
} from '../../exercises/ts/payment-events.js';

const fold = (events: PaymentEvent[]): PaymentView | undefined =>
  events.reduce<PaymentView | undefined>((view, event) => applyEvent(view, event), undefined);

describe('applyEvent', { tags: ['@exercise'] }, () => {
  test('authorized starts a view with nothing captured or refunded', () => {
    expect(applyEvent(undefined, { type: 'authorized', paymentId: 'pay_1', amountMinor: 5000 })).toEqual({
      paymentId: 'pay_1',
      status: 'authorized',
      authorizedMinor: 5000,
      capturedMinor: 0,
      refundedMinor: 0,
    });
  });

  test('capture, then a partial and a full refund', () => {
    const captured = fold([
      { type: 'authorized', paymentId: 'pay_2', amountMinor: 5000 },
      { type: 'captured', paymentId: 'pay_2', amountMinor: 4000 },
    ]);
    expect(captured).toMatchObject({ status: 'captured', capturedMinor: 4000, refundedMinor: 0 });

    const partial = applyEvent(captured, {
      type: 'refunded',
      paymentId: 'pay_2',
      amountMinor: 1500,
      reason: 'damaged',
    });
    expect(partial).toMatchObject({ status: 'partially_refunded', refundedMinor: 1500 });

    const full = applyEvent(partial, {
      type: 'refunded',
      paymentId: 'pay_2',
      amountMinor: 2500,
      reason: 'returned',
    });
    expect(full).toMatchObject({ status: 'refunded', refundedMinor: 4000 });
  });

  test('never mutates the view it is given', () => {
    const view = fold([{ type: 'authorized', paymentId: 'pay_3', amountMinor: 900 }])!;
    const before = { ...view };
    applyEvent(view, { type: 'captured', paymentId: 'pay_3', amountMinor: 900 });
    expect(view).toEqual(before);
  });

  test('a capture above the authorized amount is a RangeError', () => {
    const view = fold([{ type: 'authorized', paymentId: 'pay_4', amountMinor: 1000 }]);
    expect(() => applyEvent(view, { type: 'captured', paymentId: 'pay_4', amountMinor: 1001 })).toThrow(
      RangeError,
    );
  });

  test('refunds above the captured amount are a RangeError', () => {
    const view = fold([
      { type: 'authorized', paymentId: 'pay_5', amountMinor: 1000 },
      { type: 'captured', paymentId: 'pay_5', amountMinor: 800 },
      { type: 'refunded', paymentId: 'pay_5', amountMinor: 500, reason: 'goodwill' },
    ]);
    expect(() =>
      applyEvent(view, { type: 'refunded', paymentId: 'pay_5', amountMinor: 301, reason: 'again' }),
    ).toThrow(RangeError);
  });

  test('capture or refund for an unknown payment throws, naming the payment', () => {
    expect(() => applyEvent(undefined, { type: 'captured', paymentId: 'pay_6', amountMinor: 1 })).toThrow(
      /pay_6/,
    );
    expect(() =>
      applyEvent(undefined, { type: 'refunded', paymentId: 'pay_7', amountMinor: 1, reason: 'x' }),
    ).toThrow(/pay_7/);
  });

  test('failed keeps the amounts and records the code, with or without a view', () => {
    const view = fold([
      { type: 'authorized', paymentId: 'pay_8', amountMinor: 700 },
      { type: 'failed', paymentId: 'pay_8', code: 'capture_timeout' },
    ]);
    expect(view).toMatchObject({ status: 'failed', authorizedMinor: 700, failureCode: 'capture_timeout' });
    expect(applyEvent(undefined, { type: 'failed', paymentId: 'pay_9', code: 'card_declined' })).toEqual({
      paymentId: 'pay_9',
      status: 'failed',
      authorizedMinor: 0,
      capturedMinor: 0,
      refundedMinor: 0,
      failureCode: 'card_declined',
    });
  });
});

describe('describeEvent', { tags: ['@exercise'] }, () => {
  test('one line per event type', () => {
    expect(describeEvent({ type: 'authorized', paymentId: 'pay_1', amountMinor: 5000 })).toBe(
      'pay_1 authorized for 5000',
    );
    expect(describeEvent({ type: 'captured', paymentId: 'pay_1', amountMinor: 4000 })).toBe(
      'pay_1 captured 4000',
    );
    expect(
      describeEvent({ type: 'refunded', paymentId: 'pay_1', amountMinor: 1500, reason: 'damaged' }),
    ).toBe('pay_1 refunded 1500 (damaged)');
    expect(describeEvent({ type: 'failed', paymentId: 'pay_1', code: 'card_declined' })).toBe(
      'pay_1 failed: card_declined',
    );
  });

  test('an event type the code does not know reaches assertNever and throws', () => {
    const unknown = { type: 'disputed', paymentId: 'pay_1' } as unknown as PaymentEvent;
    expect(() => describeEvent(unknown)).toThrow(/Unexpected value/);
    expect(() => applyEvent(undefined, unknown)).toThrow(/Unexpected value/);
  });
});
