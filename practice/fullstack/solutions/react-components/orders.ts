// Shared data for the react-components exercises. Complete - you don't need to change this file.
// SandPay and every order here are fictional.

export type OrderStatus = 'PENDING' | 'SUCCEEDED' | 'FAILED' | 'REFUNDED';

export interface Order {
  /** Stable id from the API, for example "ORD-1001". */
  id: string;
  customer: string;
  /** Amount in minor units (paise, cents): 125000 is 1,250.00. Never a floating-point major amount. */
  amountMinor: number;
  currency: 'INR' | 'EUR' | 'USD';
  status: OrderStatus;
}

const twoDecimals = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** 125000 INR -> "INR 1,250.00". Only for two-decimal currencies, which is all this dashboard shows. */
export function formatAmount(amountMinor: number, currency: Order['currency']): string {
  return `${currency} ${twoDecimals.format(amountMinor / 100)}`;
}

export const sampleOrders: Order[] = [
  { id: 'ORD-1001', customer: 'Asha Rao', amountMinor: 125000, currency: 'INR', status: 'SUCCEEDED' },
  { id: 'ORD-1002', customer: 'Lukas Weber', amountMinor: 4999, currency: 'EUR', status: 'PENDING' },
  { id: 'ORD-1003', customer: 'Maria Lopez', amountMinor: 89900, currency: 'USD', status: 'FAILED' },
];
