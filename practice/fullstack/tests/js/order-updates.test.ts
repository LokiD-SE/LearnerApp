import { currencyOf, customerLabel, withStatus } from '../../exercises/js/order-updates.js';

describe('order updates', { tags: ['@exercise'] }, () => {
  const order = () => ({
    id: 'ord_1001',
    status: 'PENDING',
    amountMinor: 2599,
    currency: 'EUR',
    customer: { name: 'Asha' },
    history: [{ at: '2026-11-14T09:00:00Z', status: 'PENDING' }],
  });

  describe('withStatus', () => {
    it('returns the order with the new status and a new history entry', () => {
      const updated = withStatus(order(), 'PAID', '2026-11-14T09:01:00Z');
      expect(updated).toEqual({
        ...order(),
        status: 'PAID',
        history: [
          { at: '2026-11-14T09:00:00Z', status: 'PENDING' },
          { at: '2026-11-14T09:01:00Z', status: 'PAID' },
        ],
      });
    });

    it('returns a new object and a new history array', () => {
      const original = order();
      const updated = withStatus(original, 'PAID', '2026-11-14T09:01:00Z');
      expect(updated).not.toBe(original);
      expect(updated.history).not.toBe(original.history);
    });

    it('does not change the order it was given, not even its history', () => {
      const original = Object.freeze({ ...order(), history: Object.freeze([...order().history]) });
      withStatus(original, 'PAID', '2026-11-14T09:01:00Z');
      expect(original).toEqual(order());
    });
  });

  describe('customerLabel', () => {
    it("shows the customer's name", () => {
      expect(customerLabel(order())).toBe('Asha');
    });
    it('shows Guest when the customer or the name is missing or null', () => {
      expect(customerLabel({ ...order(), customer: undefined })).toBe('Guest');
      expect(customerLabel({ ...order(), customer: null })).toBe('Guest');
      expect(customerLabel({ ...order(), customer: {} })).toBe('Guest');
    });
    it('keeps an empty name the merchant typed on purpose', () => {
      expect(customerLabel({ ...order(), customer: { name: '' } })).toBe('');
    });
  });

  describe('currencyOf', () => {
    it('returns the currency, or EUR when it is missing', () => {
      expect(currencyOf(order())).toBe('EUR');
      expect(currencyOf({ ...order(), currency: 'INR' })).toBe('INR');
      expect(currencyOf({ ...order(), currency: undefined })).toBe('EUR');
    });
  });
});
