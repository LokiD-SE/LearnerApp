// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import {
  RefundForm,
  type RefundOrder,
  type RefundRequest,
  type RefundResult,
} from '../../exercises/react-forms/RefundForm.js';

// A fictional SandPay order: 50.00 EUR captured, 20.00 EUR already refunded - 30.00 EUR refundable.
const order: RefundOrder = { id: 'ord_1001', currency: 'EUR', capturedMinor: 5000, refundedMinor: 2000 };

/** A fake SandPay API whose answers the test settles itself - no timers, no network. */
function fakeApi() {
  const calls: RefundRequest[] = [];
  const pending: { resolve: (r: RefundResult) => void; reject: (e: Error) => void }[] = [];
  const submitRefund = (request: RefundRequest) => {
    calls.push(request);
    return new Promise<RefundResult>((resolve, reject) => pending.push({ resolve, reject }));
  };
  let n = 0;
  const newKey = () => `idem_${++n}`;
  return { calls, pending, submitRefund, newKey };
}

function setup() {
  const api = fakeApi();
  const user = userEvent.setup();
  render(<RefundForm order={order} submitRefund={api.submitRefund} newKey={api.newKey} />);
  const amount = screen.getByRole('textbox', { name: 'Amount (EUR)' });
  const reason = screen.getByRole('combobox', { name: 'Reason' });
  const button = screen.getByRole('button', { name: /refund/i });
  return { api, user, amount, reason, button };
}

describe('RefundForm', { tags: ['@exercise'] }, () => {
  it('is a controlled form: what you type is what is shown', async () => {
    const { user, amount } = setup();
    await user.type(amount, '12.50');
    expect(amount).toHaveProperty('value', '12.50');
  });

  it('an empty submit shows both errors, marks the fields invalid, focuses the first and sends nothing', async () => {
    const { api, user, amount, reason, button } = setup();
    await user.click(button);
    expect(api.calls).toHaveLength(0);
    expect(amount.getAttribute('aria-invalid')).toBe('true');
    expect(reason.getAttribute('aria-invalid')).toBe('true');
    expect(screen.getByText('Enter the amount to refund.')).toBeTruthy();
    expect(screen.getByText('Choose a reason.')).toBeTruthy();
    expect(document.activeElement).toBe(amount);
  });

  it('each error is the field description, so a screen reader reads it with the field', async () => {
    const { user, amount, reason, button } = setup();
    await user.click(button);
    expect(amount.getAttribute('aria-describedby')).toBeTruthy();
    const amountDescription = (amount.getAttribute('aria-describedby') ?? '')
      .split(' ')
      .map((id) => document.getElementById(id)?.textContent)
      .join(' ');
    expect(amountDescription).toContain('Enter the amount to refund.');
    const reasonDescription = document.getElementById(reason.getAttribute('aria-describedby') ?? '');
    expect(reasonDescription?.textContent).toBe('Choose a reason.');
  });

  it('checks the amount format, zero and the refundable limit, with a suggestion', async () => {
    const { user, amount, reason, button } = setup();
    await user.selectOptions(reason, 'duplicate');
    for (const [typed, message] of [
      ['12,50', 'Enter the amount like 12.50.'],
      ['1.234', 'Enter the amount like 12.50.'],
      ['0.00', 'The amount must be more than 0.00.'],
      ['30.01', 'You can refund at most 30.00 EUR.'],
    ] as const) {
      await user.clear(amount);
      await user.type(amount, typed);
      await user.click(button);
      expect(screen.getByText(message)).toBeTruthy();
      expect(document.activeElement).toBe(amount);
    }
  });

  it('after a failed submit, an error disappears as soon as the field is corrected', async () => {
    const { user, amount, reason, button } = setup();
    await user.click(button);
    await user.type(amount, '5');
    expect(screen.queryByText('Enter the amount to refund.')).toBeNull();
    expect(amount.getAttribute('aria-invalid')).toBeNull();
    expect(reason.getAttribute('aria-invalid')).toBe('true');
  });

  it('sends one request in minor units with an idempotency key, and disables the button while it runs', async () => {
    const { api, user, amount, reason, button } = setup();
    await user.type(amount, '30');
    await user.selectOptions(reason, 'damaged');
    await user.click(button);
    expect(api.calls).toEqual([
      { orderId: 'ord_1001', amountMinor: 3000, reason: 'damaged', idempotencyKey: 'idem_1' },
    ]);
    expect(button).toHaveProperty('disabled', true);
    // A second submit while the first is in flight (Enter key, a double click) sends nothing.
    fireEvent.submit(button.closest('form')!);
    expect(api.calls).toHaveLength(1);
  });

  it('a successful refund replaces the form with a status message', async () => {
    const { api, user, amount, reason, button } = setup();
    await user.type(amount, '7.5');
    await user.selectOptions(reason, 'requested_by_customer');
    await user.click(button);
    expect(api.calls[0]?.amountMinor).toBe(750);
    api.pending[0]?.resolve({ ok: true, refundId: 're_2001' });
    expect((await screen.findByRole('status')).textContent).toBe('Refund re_2001 created.');
  });

  it('shows the server field errors on the right field and focuses it', async () => {
    const { api, user, amount, reason, button } = setup();
    await user.type(amount, '10');
    await user.selectOptions(reason, 'duplicate');
    await user.click(button);
    api.pending[0]?.resolve({
      ok: false,
      fieldErrors: { amount: 'A refund is already pending for this order.' },
    });
    expect(await screen.findByText('A refund is already pending for this order.')).toBeTruthy();
    expect(amount.getAttribute('aria-invalid')).toBe('true');
    expect(document.activeElement).toBe(amount);
    expect(button).toHaveProperty('disabled', false);
  });

  it('after a network failure it says the outcome is unknown, and a retry reuses the idempotency key', async () => {
    const { api, user, amount, reason, button } = setup();
    await user.type(amount, '10');
    await user.selectOptions(reason, 'duplicate');
    await user.click(button);
    api.pending[0]?.reject(new Error('Network error'));
    expect((await screen.findByRole('alert')).textContent).toMatch(/may not have been created/);
    await user.click(button);
    expect(api.calls).toHaveLength(2);
    expect(api.calls[1]?.idempotencyKey).toBe(api.calls[0]?.idempotencyKey);
  });

  it('a changed request gets a new idempotency key', async () => {
    const { api, user, amount, reason, button } = setup();
    await user.type(amount, '10');
    await user.selectOptions(reason, 'duplicate');
    await user.click(button);
    api.pending[0]?.reject(new Error('Network error'));
    await screen.findByRole('alert');
    await user.clear(amount);
    await user.type(amount, '11');
    await user.click(button);
    expect(api.calls[1]?.amountMinor).toBe(1100);
    expect(api.calls[1]?.idempotencyKey).not.toBe(api.calls[0]?.idempotencyKey);
  });
});
