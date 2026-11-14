import request from 'supertest';
import { createOrdersApp, type Order, type OrderStore } from '../../exercises/express/orders-app.js';

function memoryStore(initial: Order[] = []): OrderStore & { orders: Order[] } {
  const orders = [...initial];
  return {
    orders,
    list: async () => [...orders],
    get: async (id) => orders.find((order) => order.id === id),
    create: async ({ amountMinor, currency }) => {
      const order: Order = { id: `ord_${1001 + orders.length}`, amountMinor, currency, status: 'PENDING' };
      orders.push(order);
      return order;
    },
  };
}

const paid: Order = { id: 'ord_1001', amountMinor: 2599, currency: 'EUR', status: 'PAID' };

describe('createOrdersApp', { tags: ['@exercise'] }, () => {
  test('GET /orders lists the orders from the store', async () => {
    const res = await request(createOrdersApp(memoryStore([paid]))).get('/orders');
    expect(res.status).toBe(200);
    expect(res.headers['content-type']).toMatch(/application\/json/);
    expect(res.body).toEqual({ orders: [paid] });
  });

  test('GET /orders/:id returns one order', async () => {
    const res = await request(createOrdersApp(memoryStore([paid]))).get('/orders/ord_1001');
    expect(res.status).toBe(200);
    expect(res.body).toEqual(paid);
  });

  test('GET /orders/:id answers 404 with a JSON error for an unknown id', async () => {
    const res = await request(createOrdersApp(memoryStore([paid]))).get('/orders/ord_9999');
    expect(res.status).toBe(404);
    expect(res.body).toEqual({ error: 'order_not_found' });
  });

  test('POST /orders creates an order: 201, Location header and the order in the body', async () => {
    const store = memoryStore([paid]);
    const res = await request(createOrdersApp(store))
      .post('/orders')
      .send({ amountMinor: 1250, currency: 'EUR' });
    expect(res.status).toBe(201);
    expect(res.headers.location).toBe('/orders/ord_1002');
    expect(res.body).toEqual({ id: 'ord_1002', amountMinor: 1250, currency: 'EUR', status: 'PENDING' });
    expect(store.orders).toHaveLength(2);
  });

  test.each([
    ['a decimal amount', { amountMinor: 12.5, currency: 'EUR' }],
    ['a zero amount', { amountMinor: 0, currency: 'EUR' }],
    ['a negative amount', { amountMinor: -100, currency: 'EUR' }],
    ['an amount sent as a string', { amountMinor: '1250', currency: 'EUR' }],
    ['a lower-case currency', { amountMinor: 1250, currency: 'eur' }],
    ['a missing currency', { amountMinor: 1250 }],
  ])('POST /orders rejects %s with 400 and creates nothing', async (_name, body) => {
    const store = memoryStore();
    const res = await request(createOrdersApp(store)).post('/orders').send(body);
    expect(res.status).toBe(400);
    expect(res.body).toEqual({ error: 'invalid_order' });
    expect(store.orders).toHaveLength(0);
  });

  test('POST /orders without a JSON Content-Type is a 400, not a crash or an empty order', async () => {
    const store = memoryStore();
    const res = await request(createOrdersApp(store))
      .post('/orders')
      .set('Content-Type', 'text/plain')
      .send('{"amountMinor":1250,"currency":"EUR"}');
    expect(res.status).toBe(400);
    expect(store.orders).toHaveLength(0);
  });

  test('a store that rejects ends in a 500 response, not a hung request', async () => {
    const broken: OrderStore = {
      list: () => Promise.reject(new Error('database unavailable')),
      get: () => Promise.reject(new Error('database unavailable')),
      create: () => Promise.reject(new Error('database unavailable')),
    };
    const app = createOrdersApp(broken);
    const list = await request(app).get('/orders').timeout(3000);
    expect(list.status).toBe(500);
    const one = await request(app).get('/orders/ord_1001').timeout(3000);
    expect(one.status).toBe(500);
  });
});
