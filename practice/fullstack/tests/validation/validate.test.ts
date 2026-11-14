import express, { type Express } from 'express';
import request from 'supertest';
import * as z from 'zod';
import {
  AppError,
  PROBLEMS,
  problemHandler,
  validateBody,
  validateQuery,
} from '../../exercises/validation/validate.js';

// The test's own schemas, so this file checks validate.ts even before refund-schema.ts is perfect
// (toFieldErrors from refund-schema.ts is still used to build the errors).
const Body = z.strictObject({ amountMinor: z.number().int().positive(), note: z.string().trim().optional() });
const Query = z.object({
  limit: z
    .string()
    .regex(/^[0-9]+$/)
    .transform(Number)
    .default(20),
});

function buildApp(): Express {
  const app = express();
  app.use((req, res, next) => {
    res.locals.requestId = 'req-test-1';
    next();
  });
  app.use(express.json({ limit: '1kb' }));
  app.post('/payments/:id/refunds', validateBody(Body), (req, res) => {
    res.status(201).json({ received: req.body });
  });
  app.get('/payments/:id/refunds', validateQuery(Query), (req, res) => {
    res.json({ query: res.locals.query });
  });
  app.get('/payments/:id', (req) => {
    throw new AppError(404, 'payment-not-found', 'Payment not found', `No payment ${req.params.id}`);
  });
  app.get('/ledger', async () => {
    throw new Error(
      'relation "ledger" does not exist: SELECT * FROM ledger WHERE secret = $1 at db-7.internal',
    );
  });
  app.use(problemHandler);
  return app;
}

const PROBLEM_JSON = /^application\/problem\+json/;

describe('validateBody', { tags: ['@exercise'] }, () => {
  test('passes the parsed data on, not the raw body', async () => {
    const res = await request(buildApp())
      .post('/payments/pay_1/refunds')
      .send({ amountMinor: 2599, note: '  late delivery  ' });
    expect(res.status).toBe(201);
    expect(res.body).toEqual({ received: { amountMinor: 2599, note: 'late delivery' } });
  });

  test('answers 422 Problem Details with one error per field', async () => {
    const res = await request(buildApp())
      .post('/payments/pay_1/refunds')
      .send({ amountMinor: -5, isAdmin: true });
    expect(res.status).toBe(422);
    expect(res.headers['content-type']).toMatch(PROBLEM_JSON);
    expect(res.body).toMatchObject({
      type: PROBLEMS + 'validation-error',
      title: 'Your request is not valid.',
      status: 422,
      requestId: 'req-test-1',
    });
    expect(res.body.errors.map((e: { pointer: string }) => e.pointer).sort()).toEqual(['#', '#/amountMinor']);
    for (const e of res.body.errors) expect(typeof e.detail).toBe('string');
  });

  test('answers 415 when the body is not JSON', async () => {
    const res = await request(buildApp())
      .post('/payments/pay_1/refunds')
      .set('Content-Type', 'text/plain')
      .send('amountMinor=2599');
    expect(res.status).toBe(415);
    expect(res.headers['content-type']).toMatch(PROBLEM_JSON);
    expect(res.body).toMatchObject({ type: PROBLEMS + 'unsupported-media-type', status: 415 });
  });
});

describe('validateQuery', { tags: ['@exercise'] }, () => {
  test('puts the parsed query in res.locals.query', async () => {
    const app = buildApp();
    expect((await request(app).get('/payments/pay_1/refunds')).body).toEqual({ query: { limit: 20 } });
    expect((await request(app).get('/payments/pay_1/refunds?limit=5')).body).toEqual({ query: { limit: 5 } });
  });

  test('answers 422 for a bad query parameter', async () => {
    const res = await request(buildApp()).get('/payments/pay_1/refunds?limit=lots');
    expect(res.status).toBe(422);
    expect(res.body.errors).toEqual([expect.objectContaining({ pointer: '#/limit' })]);
  });
});

describe('problemHandler', { tags: ['@exercise'] }, () => {
  test('maps malformed and oversized JSON to 400 and 413', async () => {
    const app = buildApp();
    const malformed = await request(app)
      .post('/payments/pay_1/refunds')
      .set('Content-Type', 'application/json')
      .send('{"amountMinor": 25');
    expect(malformed.status).toBe(400);
    expect(malformed.headers['content-type']).toMatch(PROBLEM_JSON);
    expect(malformed.body).toMatchObject({
      type: PROBLEMS + 'malformed-json',
      status: 400,
      requestId: 'req-test-1',
    });

    const huge = await request(app)
      .post('/payments/pay_1/refunds')
      .send({ note: 'x'.repeat(5000) });
    expect(huge.status).toBe(413);
    expect(huge.body).toMatchObject({ type: PROBLEMS + 'payload-too-large', status: 413 });
  });

  test('sends an AppError as written for the client', async () => {
    const res = await request(buildApp()).get('/payments/pay_404');
    expect(res.status).toBe(404);
    expect(res.headers['content-type']).toMatch(PROBLEM_JSON);
    expect(res.body).toEqual({
      type: PROBLEMS + 'payment-not-found',
      title: 'Payment not found',
      status: 404,
      detail: 'No payment pay_404',
      requestId: 'req-test-1',
    });
  });

  test('answers unexpected errors with a generic 500 and logs the real error', async () => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => {});
    try {
      const res = await request(buildApp()).get('/ledger');
      expect(res.status).toBe(500);
      expect(res.headers['content-type']).toMatch(PROBLEM_JSON);
      expect(res.body).toEqual({
        type: PROBLEMS + 'internal-error',
        title: 'Internal Server Error',
        status: 500,
        requestId: 'req-test-1',
      });
      expect(res.text).not.toMatch(/SELECT|ledger|db-7|secret|at \//);
      const logged = log.mock.calls.flat().map(String).join(' ');
      expect(logged).toContain('req-test-1');
      expect(log.mock.calls.flat().some((a) => a instanceof Error && a.message.includes('SELECT'))).toBe(
        true,
      );
    } finally {
      log.mockRestore();
    }
  });
});
