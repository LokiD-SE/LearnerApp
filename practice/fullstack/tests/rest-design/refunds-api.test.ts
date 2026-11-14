import request from 'supertest';
import { createRefundsApp } from '../../exercises/rest-design/refunds-api.js';
import { PROBLEMS } from '../../exercises/rest-design/problem.js';
import { SandPayStore } from '../../exercises/rest-design/sandpay-store.js';

const NOW = new Date('2026-11-14T09:30:00.000Z');

function setup() {
  const store = new SandPayStore(
    [
      {
        id: 'pay_1001',
        amountMinor: 5000,
        currency: 'EUR',
        status: 'captured',
        createdAt: '2026-11-13T10:00:00.000Z',
      },
      {
        id: 'pay_1002',
        amountMinor: 2500,
        currency: 'INR',
        status: 'authorized',
        createdAt: '2026-11-13T11:00:00.000Z',
      },
    ],
    () => NOW,
  );
  return { store, app: createRefundsApp(store) };
}

const refundBody = { amountMinor: 1200, reason: 'Item returned' };

function expectProblem(response: request.Response, status: number, type?: string) {
  expect(response.status).toBe(status);
  expect(response.headers['content-type']).toMatch(/^application\/problem\+json/);
  expect(response.body.status).toBe(status);
  expect(typeof response.body.title).toBe('string');
  if (type) expect(response.body.type).toBe(`${PROBLEMS}${type}`);
}

describe('refunds API', { tags: ['@exercise'] }, () => {
  describe('POST /payments/:paymentId/refunds', () => {
    test('creates a refund: 201, Location of the new resource, ETag and the representation', async () => {
      const { app } = setup();
      const response = await request(app).post('/payments/pay_1001/refunds').send(refundBody);

      expect(response.status).toBe(201);
      expect(response.headers.location).toBe('/payments/pay_1001/refunds/re_0001');
      expect(response.headers.etag).toMatch(/^"[^"]+"$/);
      expect(response.headers['content-type']).toMatch(/^application\/json/);
      expect(response.body).toEqual({
        id: 're_0001',
        paymentId: 'pay_1001',
        amountMinor: 1200,
        currency: 'EUR',
        reason: 'Item returned',
        status: 'pending',
        createdAt: '2026-11-14T09:30:00.000Z',
      });
    });

    test('the Location can be fetched and returns the same refund and ETag', async () => {
      const { app } = setup();
      const created = await request(app).post('/payments/pay_1001/refunds').send(refundBody);
      const fetched = await request(app).get(created.headers.location as string);

      expect(fetched.status).toBe(200);
      expect(fetched.body).toEqual(created.body);
      expect(fetched.headers.etag).toBe(created.headers.etag);
    });

    test('an unknown payment is a 404 problem', async () => {
      const { app } = setup();
      expectProblem(
        await request(app).post('/payments/pay_9999/refunds').send(refundBody),
        404,
        'payment-not-found',
      );
    });

    test('invalid fields are one 422 problem listing every error with a JSON pointer', async () => {
      const { app } = setup();
      const response = await request(app)
        .post('/payments/pay_1001/refunds')
        .send({ amountMinor: 12.5, reason: '' });

      expectProblem(response, 422, 'validation-error');
      const pointers = (response.body.errors as { pointer: string; detail: string }[])
        .map((e) => e.pointer)
        .sort();
      expect(pointers).toEqual(['#/amountMinor', '#/reason']);
    });

    test('zero, negative and string amounts are rejected', async () => {
      const { app } = setup();
      for (const amountMinor of [0, -100, '1200']) {
        const response = await request(app)
          .post('/payments/pay_1001/refunds')
          .send({ amountMinor, reason: 'x' });
        expectProblem(response, 422, 'validation-error');
      }
    });

    test('refunding more than is left is a 409 conflict that says how much is refundable', async () => {
      const { app } = setup();
      await request(app).post('/payments/pay_1001/refunds').send({ amountMinor: 4000, reason: 'Most of it' });
      const response = await request(app)
        .post('/payments/pay_1001/refunds')
        .send({ amountMinor: 1500, reason: 'Too much' });

      expectProblem(response, 409, 'refund-exceeds-captured');
      expect(response.body.refundableMinor).toBe(1000);
    });

    test('a payment that was never captured has nothing to refund', async () => {
      const { app } = setup();
      const response = await request(app)
        .post('/payments/pay_1002/refunds')
        .send({ amountMinor: 100, reason: 'x' });
      expectProblem(response, 409, 'refund-exceeds-captured');
      expect(response.body.refundableMinor).toBe(0);
    });

    test('malformed JSON is a 400 problem, not an HTML error page', async () => {
      const { app } = setup();
      const response = await request(app)
        .post('/payments/pay_1001/refunds')
        .set('Content-Type', 'application/json')
        .send('{"amountMinor": 12');
      expectProblem(response, 400);
    });
  });

  describe('GET /payments/:paymentId/refunds/:refundId', () => {
    test('a refund under another payment is not found', async () => {
      const { app } = setup();
      await request(app).post('/payments/pay_1001/refunds').send(refundBody);
      expectProblem(await request(app).get('/payments/pay_1002/refunds/re_0001'), 404, 'refund-not-found');
      expectProblem(await request(app).get('/payments/pay_1001/refunds/re_9999'), 404, 'refund-not-found');
    });
  });

  describe('PATCH /payments/:paymentId/refunds/:refundId (optimistic concurrency)', () => {
    async function created() {
      const ctx = setup();
      const response = await request(ctx.app).post('/payments/pay_1001/refunds').send(refundBody);
      return { ...ctx, url: response.headers.location as string, etag: response.headers.etag as string };
    }

    const patch = (app: Parameters<typeof request>[0], url: string) =>
      request(app).patch(url).set('Content-Type', 'application/merge-patch+json');

    test('with the current ETag in If-Match: 200, the change and a new ETag', async () => {
      const { app, url, etag } = await created();
      const response = await patch(app, url).set('If-Match', etag).send({ reason: 'Damaged on arrival' });

      expect(response.status).toBe(200);
      expect(response.body.reason).toBe('Damaged on arrival');
      expect(response.body.amountMinor).toBe(1200);
      expect(response.headers.etag).toMatch(/^"[^"]+"$/);
      expect(response.headers.etag).not.toBe(etag);
      expect((await request(app).get(url)).headers.etag).toBe(response.headers.etag);
    });

    test('without If-Match: 428 Precondition Required, and nothing changes', async () => {
      const { app, url } = await created();
      expectProblem(await patch(app, url).send({ reason: 'Changed' }), 428, 'precondition-required');
      expect((await request(app).get(url)).body.reason).toBe('Item returned');
    });

    test('a stale ETag (someone else changed it first): 412, and the lost update is prevented', async () => {
      const { app, url, etag } = await created();
      const first = await patch(app, url).set('If-Match', etag).send({ reason: 'First editor' });
      expect(first.status).toBe(200);

      const second = await patch(app, url).set('If-Match', etag).send({ reason: 'Second editor' });
      expectProblem(second, 412, 'precondition-failed');
      expect((await request(app).get(url)).body.reason).toBe('First editor');
    });

    test('If-Match uses the strong comparison: a weak tag never matches', async () => {
      const { app, url, etag } = await created();
      expectProblem(
        await patch(app, url).set('If-Match', `W/${etag}`).send({ reason: 'x' }),
        412,
        'precondition-failed',
      );
    });

    test('If-Match accepts a list of tags and *', async () => {
      const { app, url, etag } = await created();
      const listed = await patch(app, url).set('If-Match', `"nope", ${etag}`).send({ reason: 'Listed' });
      expect(listed.status).toBe(200);
      const star = await patch(app, url).set('If-Match', '*').send({ reason: 'Any version' });
      expect(star.status).toBe(200);
    });

    test('only reason can change: other fields are a 422 naming them', async () => {
      const { app, url, etag } = await created();
      const response = await patch(app, url).set('If-Match', etag).send({ amountMinor: 1 });
      expectProblem(response, 422, 'validation-error');
      expect(response.body.errors).toEqual([expect.objectContaining({ pointer: '#/amountMinor' })]);
    });

    test('a body that is not merge-patch+json: 415 with Accept-Patch, checked before the preconditions', async () => {
      const { app, url } = await created();
      const response = await request(app).patch(url).send({ reason: 'Plain JSON' }); // application/json, no If-Match
      expectProblem(response, 415, 'unsupported-media-type');
      expect(response.headers['accept-patch']).toBe('application/merge-patch+json');
    });

    test('an unknown refund is 404 even without If-Match', async () => {
      const { app } = await created();
      expectProblem(
        await patch(app, '/payments/pay_1001/refunds/re_9999').send({ reason: 'x' }),
        404,
        'refund-not-found',
      );
    });
  });
});
