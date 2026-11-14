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
  // TODO: parse JSON bodies, add the three routes above, and use `store` for every read and write.
  void store;
  return app;
}
