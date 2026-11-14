// Shared types for the react-routing exercises. Complete - you don't need to change this file.
// SandPay and every order here are fictional.

export type OrderStatus = 'PENDING' | 'SUCCEEDED' | 'FAILED' | 'REFUNDED';

export interface Order {
  /** Stable id from the API, for example "ORD-1001". */
  id: string;
  customer: string;
  /** Amount in minor units (paise, cents): 125000 is 1,250.00. */
  amountMinor: number;
  currency: 'INR' | 'EUR' | 'USD';
  status: OrderStatus;
}

/** What the routes need from the backend. The tests pass a fake; the app passes one built on apiGet. */
export interface OrdersApi {
  listOrders(signal: AbortSignal): Promise<Order[]>;
  /** Resolves to null when the order does not exist. */
  getOrder(orderId: string, signal: AbortSignal): Promise<Order | null>;
}

const twoDecimals = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** 125000 INR -> "INR 1,250.00". */
export function formatAmount(amountMinor: number, currency: Order['currency']): string {
  return `${currency} ${twoDecimals.format(amountMinor / 100)}`;
}
