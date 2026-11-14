// Shared by both rest-design exercises - you don't need to change this file.
// An in-memory stand-in for the SandPay merchant dashboard's database. Every name, id and amount is
// fictional; amounts are integers in minor units (cents, paise).

export interface Payment {
  id: string;
  amountMinor: number;
  currency: string;
  status: 'authorized' | 'captured' | 'failed';
  /** RFC 3339 timestamp in UTC, for example 2026-11-14T09:30:00.000Z. */
  createdAt: string;
}

export interface Refund {
  id: string;
  paymentId: string;
  amountMinor: number;
  currency: string;
  reason: string;
  status: 'pending' | 'succeeded' | 'failed';
  createdAt: string;
  /** Increases by one on every change. The API turns it into the ETag. */
  version: number;
}

export class SandPayStore {
  readonly payments: Payment[];
  readonly refunds = new Map<string, Refund>();
  private nextRefund = 1;

  constructor(
    payments: Payment[],
    private readonly now: () => Date = () => new Date(),
  ) {
    this.payments = [...payments];
  }

  findPayment(id: string): Payment | undefined {
    return this.payments.find((payment) => payment.id === id);
  }

  refundsFor(paymentId: string): Refund[] {
    return [...this.refunds.values()].filter((refund) => refund.paymentId === paymentId);
  }

  addRefund(input: { paymentId: string; amountMinor: number; currency: string; reason: string }): Refund {
    const id = `re_${String(this.nextRefund++).padStart(4, '0')}`;
    const refund: Refund = {
      id,
      ...input,
      status: 'pending',
      createdAt: this.now().toISOString(),
      version: 1,
    };
    this.refunds.set(id, refund);
    return refund;
  }

  /** Replaces a refund with an updated copy and bumps its version. */
  updateRefund(id: string, changes: Partial<Pick<Refund, 'reason'>>): Refund {
    const current = this.refunds.get(id);
    if (!current) throw new Error(`no refund ${id}`);
    const updated = { ...current, ...changes, version: current.version + 1 };
    this.refunds.set(id, updated);
    return updated;
  }
}
