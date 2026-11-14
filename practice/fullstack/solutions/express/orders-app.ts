// Exercise: the first routes of the SandPay merchant API (fictional) - list, read and create orders.
// Tests: tests/express/orders-app.test.ts

import express, { type Express } from 'express';

export interface Order {
  id: string;
  /** Integer minor units: 2599 is 25.99. */
  amountMinor: number;
  /** ISO 4217 code: three capital letters. */
  currency: string;
  status: 'PENDING' | 'PAID' | 'FAILED';
}

/** Where orders live. Every method is asynchronous, like a real database call, and may reject. */
export interface OrderStore {
  list(): Promise<Order[]>;
  get(id: string): Promise<Order | undefined>;
  create(input: { amountMinor: number; currency: string }): Promise<Order>;
}

/**
 * Builds the app WITHOUT calling listen(), so tests (and server.ts) decide where it runs.
 *
 * - `GET /orders` -> 200 `{ "orders": [...] }`
 * - `GET /orders/:id` -> 200 with the order, or 404 `{ "error": "order_not_found" }`
 * - `POST /orders` with a JSON body `{ "amountMinor": 1250, "currency": "EUR" }` ->
 *   201 with the created order and a `Location: /orders/<id>` header. A missing body, an
 *   `amountMinor` that isn't a positive integer, or a `currency` that isn't three capital letters ->
 *   400 `{ "error": "invalid_order" }`, and nothing is created.
 * - A store that rejects must end in a 500 response, never a request that hangs.
 */
export function createOrdersApp(store: OrderStore): Express {
  const app = express();
  app.use(express.json());

  app.get('/orders', async (req, res) => {
    res.json({ orders: await store.list() });
  });

  app.get('/orders/:id', async (req, res) => {
    const order = await store.get(req.params.id);
    if (!order) {
      res.status(404).json({ error: 'order_not_found' });
      return;
    }
    res.json(order);
  });

  app.post('/orders', async (req, res) => {
    // Express 5: req.body is undefined when no parser ran (no JSON Content-Type), so guard it.
    const body: unknown = req.body;
    const { amountMinor, currency } = (typeof body === 'object' && body !== null ? body : {}) as Record<
      string,
      unknown
    >;
    const validAmount = Number.isSafeInteger(amountMinor) && (amountMinor as number) > 0;
    const validCurrency = typeof currency === 'string' && /^[A-Z]{3}$/.test(currency);
    if (!validAmount || !validCurrency) {
      res.status(400).json({ error: 'invalid_order' });
      return;
    }
    const order = await store.create({ amountMinor: amountMinor as number, currency: currency as string });
    res.status(201).location(`/orders/${order.id}`).json(order);
  });

  return app;
}
