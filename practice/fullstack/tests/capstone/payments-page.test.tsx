// @vitest-environment jsdom
import { render, screen, within } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import {
  PaymentsPage,
  type DashboardClient,
  type PaymentRow,
  type RefundResult,
} from '../../exercises/capstone/PaymentsPage.js';

// Fictional SandPay payments for merchant Asha Books, newest first (as GET /api/payments returns them).
const rows = (): PaymentRow[] => [
  {
    id: 'pay_1002',
    amountMinor: 1250,
    currency: 'EUR',
    refundedMinor: 0,
    refundableMinor: 1250,
    createdAt: '2026-11-12T14:02:00Z',
  },
  {
    id: 'pay_1001',
    amountMinor: 5000,
    currency: 'EUR',
    refundedMinor: 1500,
    refundableMinor: 3500,
    createdAt: '2026-11-10T09:15:00Z',
  },
  {
    id: 'pay_1003',
    amountMinor: 2599,
    currency: 'EUR',
    refundedMinor: 2599,
    refundableMinor: 0,
    createdAt: '2026-11-01T08:30:00Z',
  },
];

/** A promise the test resolves or rejects when it chooses - to see in-flight states. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function setup(client: Partial<DashboardClient> = {}) {
  const full: DashboardClient = {
    listPayments: vi.fn(async () => rows()),
    refund: vi.fn(async (): Promise<RefundResult> => ({ ok: true, refundableMinor: 0 })),
    ...client,
  };
  let n = 0;
  const newKey = vi.fn(() => `key-${++n}`);
  const user = userEvent.setup();
  render(<PaymentsPage client={full} newKey={newKey} />);
  return { client: full, newKey, user };
}

const row = (id: string) => screen.getByRole('row', { name: new RegExp(`^${id}`) });

describe('capstone payments page: loading the list', { tags: ['@exercise'] }, () => {
  it('shows a loading status, then the table with formatted amounts and actions', async () => {
    setup();
    expect(screen.getByRole('status').textContent).toBe('Loading payments...');
    await screen.findByRole('table', { name: 'Payments' });
    expect(
      within(row('pay_1002'))
        .getAllByRole('cell')
        .map((c) => c.textContent),
    ).toEqual(['2026-11-12', '€12.50', '€12.50', 'Refund €12.50 on pay_1002']);
    expect(within(row('pay_1001')).getByRole('button').textContent).toBe('Refund €35.00 on pay_1001');
    expect(within(row('pay_1003')).queryByRole('button')).toBeNull();
    expect(within(row('pay_1003')).getByText('Fully refunded')).toBeTruthy();
  });

  it('a failed load shows an alert, and Retry loads again', async () => {
    const listPayments = vi
      .fn<DashboardClient['listPayments']>()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(rows());
    const { user } = setup({ listPayments });
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('Could not load payments.');
    await user.click(within(alert).getByRole('button', { name: 'Retry' }));
    await screen.findByRole('table', { name: 'Payments' });
    expect(listPayments).toHaveBeenCalledTimes(2);
  });

  it('an empty list says so', async () => {
    setup({ listPayments: async () => [] });
    expect(await screen.findByText('No payments yet.')).toBeTruthy();
  });
});

describe('capstone payments page: refunding', { tags: ['@exercise'] }, () => {
  it('a refund updates the row and announces it', async () => {
    const { client, user } = setup();
    await user.click(await screen.findByRole('button', { name: 'Refund €12.50 on pay_1002' }));
    expect(client.refund).toHaveBeenCalledWith('pay_1002', 1250, 'key-1');
    expect((await screen.findByText('Refunded €12.50 on pay_1002.')).getAttribute('role')).toBe('status');
    expect(within(row('pay_1002')).getByText('Fully refunded')).toBeTruthy();
  });

  it('while a refund is in flight every refund button is disabled - a double click refunds once', async () => {
    const answer = deferred<RefundResult>();
    const { client, user } = setup({ refund: vi.fn(() => answer.promise) });
    const button = await screen.findByRole('button', { name: 'Refund €12.50 on pay_1002' });
    await user.dblClick(button);
    expect(client.refund).toHaveBeenCalledTimes(1);
    for (const b of screen.getAllByRole('button')) expect((b as HTMLButtonElement).disabled).toBe(true);
    answer.resolve({ ok: true, refundableMinor: 0 });
    await screen.findByText('Refunded €12.50 on pay_1002.');
    expect(
      (screen.getByRole('button', { name: 'Refund €35.00 on pay_1001' }) as HTMLButtonElement).disabled,
    ).toBe(false);
  });

  it('a refused refund shows the reason and offers no retry', async () => {
    const { user } = setup({
      refund: async () => ({ ok: false, title: 'Refund exceeds the refundable amount' }),
    });
    await user.click(await screen.findByRole('button', { name: 'Refund €35.00 on pay_1001' }));
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe('Refund failed: Refund exceeds the refundable amount');
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull();
  });

  it('no answer: Try again resends the same refund with the SAME key', async () => {
    const refund = vi
      .fn<DashboardClient['refund']>()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce({ ok: true, refundableMinor: 0 });
    const { user, newKey } = setup({ refund });
    await user.click(await screen.findByRole('button', { name: 'Refund €12.50 on pay_1002' }));
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('The refund on pay_1002 did not complete.');
    await user.click(within(alert).getByRole('button', { name: 'Try again' }));
    await screen.findByText('Refunded €12.50 on pay_1002.');
    expect(refund.mock.calls).toEqual([
      ['pay_1002', 1250, 'key-1'],
      ['pay_1002', 1250, 'key-1'],
    ]);
    expect(newKey).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('a new refund after a success gets a new key', async () => {
    const { client, user } = setup({
      refund: vi.fn(async () => ({ ok: true as const, refundableMinor: 0 })),
    });
    await user.click(await screen.findByRole('button', { name: 'Refund €12.50 on pay_1002' }));
    await screen.findByText('Refunded €12.50 on pay_1002.');
    await user.click(screen.getByRole('button', { name: 'Refund €35.00 on pay_1001' }));
    await screen.findByText('Refunded €35.00 on pay_1001.');
    expect(vi.mocked(client.refund).mock.calls.map((c) => c[2])).toEqual(['key-1', 'key-2']);
  });
});
