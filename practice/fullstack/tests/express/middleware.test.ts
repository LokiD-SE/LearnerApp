import express, { type Express } from 'express';
import request from 'supertest';
import { errorHandler, notFound, requestId } from '../../exercises/express/middleware.js';

/** A small app wired the way the lesson recommends: request id first, error handler last. */
function buildApp(): Express {
  const app = express();
  app.use(requestId());
  app.use(express.json({ limit: '1kb' }));
  app.get('/orders/ord_1001', (req, res) => {
    res.json({ id: 'ord_1001', requestId: res.locals.requestId });
  });
  app.post('/orders', (req, res) => {
    res.status(201).json(req.body);
  });
  app.get('/ledger', async () => {
    throw new Error('ledger timeout at db-7.internal:5432');
  });
  app.get('/partial', (req, res, next) => {
    res.status(200).write('{"rows":[');
    next(new Error('stream broke'));
  });
  app.use(notFound);
  app.use(errorHandler);
  return app;
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

describe('requestId', { tags: ['@exercise'] }, () => {
  test('generates an id, sends it back and shares it through res.locals', async () => {
    const res = await request(buildApp()).get('/orders/ord_1001');
    expect(res.status).toBe(200);
    expect(res.headers['x-request-id']).toMatch(uuid);
    expect(res.body.requestId).toBe(res.headers['x-request-id']);
  });

  test('generates a different id for every request', async () => {
    const app = buildApp();
    const first = await request(app).get('/orders/ord_1001');
    const second = await request(app).get('/orders/ord_1001');
    expect(first.headers['x-request-id']).not.toBe(second.headers['x-request-id']);
  });

  test('reuses a safe incoming X-Request-Id', async () => {
    const res = await request(buildApp()).get('/orders/ord_1001').set('X-Request-Id', 'checkout-7f3a');
    expect(res.headers['x-request-id']).toBe('checkout-7f3a');
    expect(res.body.requestId).toBe('checkout-7f3a');
  });

  test('replaces an unsafe or oversized incoming id', async () => {
    const app = buildApp();
    const injected = await request(app).get('/orders/ord_1001').set('X-Request-Id', 'abc"><script>');
    expect(injected.headers['x-request-id']).toMatch(uuid);
    const long = await request(app).get('/orders/ord_1001').set('X-Request-Id', 'a'.repeat(65));
    expect(long.headers['x-request-id']).toMatch(uuid);
  });
});

describe('notFound', { tags: ['@exercise'] }, () => {
  test('answers unknown routes with a JSON 404 that carries the request id', async () => {
    const res = await request(buildApp()).get('/refunds');
    expect(res.status).toBe(404);
    expect(res.headers['content-type']).toMatch(/application\/json/);
    expect(res.body).toEqual({ error: 'not_found', requestId: res.headers['x-request-id'] });
  });
});

describe('errorHandler', { tags: ['@exercise'] }, () => {
  test('turns malformed JSON into 400 malformed_json', async () => {
    const res = await request(buildApp())
      .post('/orders')
      .set('Content-Type', 'application/json')
      .send('{"amountMinor":1250,');
    expect(res.status).toBe(400);
    expect(res.body).toEqual({ error: 'malformed_json', requestId: res.headers['x-request-id'] });
  });

  test('turns a body over the limit into 413 payload_too_large', async () => {
    const res = await request(buildApp())
      .post('/orders')
      .send({ note: 'x'.repeat(2000) });
    expect(res.status).toBe(413);
    expect(res.body).toEqual({ error: 'payload_too_large', requestId: res.headers['x-request-id'] });
  });

  test('answers an unexpected error with 500 and leaks neither the message nor the stack', async () => {
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {});
    try {
      const res = await request(buildApp()).get('/ledger');
      expect(res.status).toBe(500);
      expect(res.headers['content-type']).toMatch(/application\/json/);
      expect(res.body).toEqual({ error: 'internal_error', requestId: res.headers['x-request-id'] });
      expect(res.text).not.toContain('ledger timeout');
      expect(res.text).not.toContain('db-7.internal');
      expect(logged).toHaveBeenCalled();
    } finally {
      logged.mockRestore();
    }
  });

  test('passes the error on when the response has already started', async () => {
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {});
    try {
      // Express's own handler closes the connection, so the client sees a broken response, not JSON.
      const outcome = await request(buildApp())
        .get('/partial')
        .timeout(3000)
        .then(
          (res) => ({ status: res.status, text: res.text }),
          (error: Error) => ({ error: error.message }),
        );
      expect(JSON.stringify(outcome)).not.toContain('internal_error');
    } finally {
      logged.mockRestore();
    }
  });
});
