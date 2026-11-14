// Shared by both openapi exercises - you don't need to change this file.
// The SandPay merchant dashboard's orders API, already built. Exercise 1 asks you to describe it in
// OpenAPI 3.1 so that the contract tests pass. Every id, amount and note is fictional; amounts are
// integers in minor units (cents, paise).
import express, { type Request, type Response } from 'express';

export const PROBLEMS = 'https://api.sandpay.example/problems/';

export interface Order {
  id: string;
  amountMinor: number;
  currency: string;
  status: 'pending' | 'paid' | 'refunded' | 'failed';
  /** Free text the customer typed at checkout, or null when they typed nothing. */
  customerNote: string | null;
  createdAt: string;
}

export interface Refund {
  id: string;
  orderId: string;
  amountMinor: number;
  reason: string;
  createdAt: string;
}

export function sampleOrders(): Order[] {
  return [
    {
      id: 'ord_1001',
      amountMinor: 5000,
      currency: 'EUR',
      status: 'paid',
      customerNote: 'Leave at the door',
      createdAt: '2026-11-13T10:00:00.000Z',
    },
    {
      id: 'ord_1002',
      amountMinor: 2500,
      currency: 'INR',
      status: 'paid',
      customerNote: null,
      createdAt: '2026-11-13T11:00:00.000Z',
    },
    {
      id: 'ord_1003',
      amountMinor: 900,
      currency: 'EUR',
      status: 'pending',
      customerNote: null,
      createdAt: '2026-11-14T08:15:00.000Z',
    },
  ];
}

function problem(res: Response, status: number, type: string, title: string, detail?: string): void {
  res
    .status(status)
    .type('application/problem+json')
    .json({ type: `${PROBLEMS}${type}`, title, status, ...(detail ? { detail } : {}) });
}

export function createOrdersApp(orders: Order[] = sampleOrders(), now: () => Date = () => new Date()) {
  const refunds: Refund[] = [];
  let nextRefund = 1;
  const app = express();
  app.set('etag', false);
  app.use(express.json());

  // GET /orders?status=paid&limit=2 - newest first, at most `limit` (1-100, default 20).
  app.get('/orders', (req: Request, res: Response) => {
    const { status, limit } = req.query;
    const size = limit === undefined ? 20 : Number(limit);
    if (!Number.isInteger(size) || size < 1 || size > 100) {
      problem(res, 400, 'invalid-query', 'Invalid query parameter', 'limit must be an integer from 1 to 100');
      return;
    }
    if (status !== undefined && !['pending', 'paid', 'refunded', 'failed'].includes(String(status))) {
      problem(res, 400, 'invalid-query', 'Invalid query parameter', 'unknown status');
      return;
    }
    const data = orders
      .filter((o) => status === undefined || o.status === status)
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
      .slice(0, size);
    res.json({ data });
  });

  app.get('/orders/:orderId', (req: Request, res: Response) => {
    const order = orders.find((o) => o.id === req.params.orderId);
    if (!order) {
      problem(res, 404, 'order-not-found', 'Order not found', `No order ${req.params.orderId}`);
      return;
    }
    res.json(order);
  });

  // POST /orders/{orderId}/refunds  { "amountMinor": 1200, "reason": "Item returned" }
  app.post('/orders/:orderId/refunds', (req: Request, res: Response) => {
    const order = orders.find((o) => o.id === req.params.orderId);
    if (!order) {
      problem(res, 404, 'order-not-found', 'Order not found', `No order ${req.params.orderId}`);
      return;
    }
    const body: unknown = req.body;
    const valid =
      typeof body === 'object' &&
      body !== null &&
      Object.keys(body).every((k) => k === 'amountMinor' || k === 'reason') &&
      'amountMinor' in body &&
      Number.isInteger(body.amountMinor) &&
      (body.amountMinor as number) >= 1 &&
      'reason' in body &&
      typeof body.reason === 'string' &&
      body.reason.length >= 1 &&
      body.reason.length <= 200;
    if (!valid) {
      problem(
        res,
        400,
        'invalid-refund',
        'Invalid refund request',
        'amountMinor (integer, at least 1) and reason (1-200 characters) are required, nothing else',
      );
      return;
    }
    const { amountMinor, reason } = body as { amountMinor: number; reason: string };
    const refunded = refunds.filter((r) => r.orderId === order.id).reduce((sum, r) => sum + r.amountMinor, 0);
    if (order.status !== 'paid' || refunded + amountMinor > order.amountMinor) {
      problem(
        res,
        409,
        'refund-exceeds-order',
        'Refund not possible',
        `At most ${order.amountMinor - refunded} can be refunded on ${order.id} (${order.status})`,
      );
      return;
    }
    const refund: Refund = {
      id: `re_${String(nextRefund++).padStart(4, '0')}`,
      orderId: order.id,
      amountMinor,
      reason,
      createdAt: now().toISOString(),
    };
    refunds.push(refund);
    res.status(201).location(`/orders/${order.id}/refunds/${refund.id}`).json(refund);
  });

  app.use((req: Request, res: Response) => {
    problem(res, 404, 'not-found', 'Not found', `${req.method} ${req.path} is not part of this API`);
  });
  return app;
}
