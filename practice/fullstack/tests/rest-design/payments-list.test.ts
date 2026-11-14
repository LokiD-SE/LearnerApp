import request from 'supertest';
import { createPaymentsListApp } from '../../exercises/rest-design/payments-list.js';
import { PROBLEMS } from '../../exercises/rest-design/problem.js';
import { type Payment, SandPayStore } from '../../exercises/rest-design/sandpay-store.js';

/** 150 payments, one a minute from 08:00 - with pairs sharing a timestamp, to test the tie-break. */
function payments(): Payment[] {
  return Array.from({ length: 150 }, (_, i) => {
    const minute = Math.floor(i / 2) * 2 + (i % 3 === 0 ? 0 : 1);
    const createdAt = new Date(Date.UTC(2026, 10, 14, 8, 0) + minute * 60_000).toISOString();
    return {
      id: `pay_${String(1000 + i)}`,
      amountMinor: 100 + i,
      currency: 'EUR',
      status: 'captured',
      createdAt,
    } satisfies Payment;
  });
}

/** The order the API must return: newest first, ties by id descending. */
function expectedOrder(list: Payment[]): string[] {
  return [...list]
    .sort((a, b) =>
      a.createdAt === b.createdAt ? b.id.localeCompare(a.id) : b.createdAt.localeCompare(a.createdAt),
    )
    .map((p) => p.id);
}

function setup() {
  const store = new SandPayStore(payments());
  return { store, app: createPaymentsListApp(store) };
}

/** Parses `Link: </payments?...>; rel="next"` into the URL, or undefined. */
function nextLink(response: request.Response): string | undefined {
  const header = response.headers.link as string | undefined;
  return header?.match(/<([^>]+)>\s*;\s*rel="next"/)?.[1];
}

function expectProblem(response: request.Response, type: string) {
  expect(response.status).toBe(400);
  expect(response.headers['content-type']).toMatch(/^application\/problem\+json/);
  expect(response.body).toMatchObject({ type: `${PROBLEMS}${type}`, status: 400 });
}

describe('GET /payments with cursor pagination', { tags: ['@exercise'] }, () => {
  test('the first page has 20 payments, newest first, a nextCursor and a Link to the next page', async () => {
    const { app, store } = setup();
    const response = await request(app).get('/payments');

    expect(response.status).toBe(200);
    expect((response.body.data as Payment[]).map((p) => p.id)).toEqual(
      expectedOrder(store.payments).slice(0, 20),
    );
    expect(typeof response.body.nextCursor).toBe('string');
    const link = nextLink(response);
    expect(link).toBeDefined();
    const url = new URL(link as string, 'https://api.sandpay.example');
    expect(url.pathname).toBe('/payments');
    expect(url.searchParams.get('cursor')).toBe(response.body.nextCursor);
    expect(url.searchParams.get('limit')).toBe('20');
  });

  test('following nextCursor visits every payment exactly once, in order; the last page has no cursor or Link', async () => {
    const { app, store } = setup();
    const seen: string[] = [];
    let response = await request(app).get('/payments').query({ limit: 40 });
    for (let pages = 1; ; pages++) {
      expect(response.status).toBe(200);
      seen.push(...(response.body.data as Payment[]).map((p) => p.id));
      if (!('nextCursor' in response.body)) {
        expect(response.headers.link).toBeUndefined();
        expect(pages).toBe(4);
        break;
      }
      expect(pages).toBeLessThan(4);
      response = await request(app).get('/payments').query({ limit: 40, cursor: response.body.nextCursor });
    }
    expect(seen).toEqual(expectedOrder(store.payments));
  });

  test('the Link header can be followed as it is', async () => {
    const { app } = setup();
    const first = await request(app).get('/payments').query({ limit: 5 });
    const second = await request(app).get(nextLink(first) as string);
    const viaCursor = await request(app).get('/payments').query({ limit: 5, cursor: first.body.nextCursor });
    expect(second.status).toBe(200);
    expect(second.body).toEqual(viaCursor.body);
  });

  test('payments created while a client is paging do not shift its pages', async () => {
    const { app, store } = setup();
    const before = expectedOrder(store.payments);
    const first = await request(app).get('/payments').query({ limit: 10 });

    for (let i = 0; i < 3; i++)
      store.payments.push({
        id: `pay_new_${i}`,
        amountMinor: 999,
        currency: 'EUR',
        status: 'captured',
        createdAt: `2026-11-14T12:0${i}:00.000Z`,
      });

    const second = await request(app).get('/payments').query({ limit: 10, cursor: first.body.nextCursor });
    expect((second.body.data as Payment[]).map((p) => p.id)).toEqual(before.slice(10, 20));
  });

  test('the cursor is opaque - not a page number or an offset', async () => {
    const { app } = setup();
    const response = await request(app).get('/payments').query({ limit: 10 });
    expect(response.body.nextCursor).not.toMatch(/^\d+$/);
    expect(response.body.nextCursor).toMatch(/^[A-Za-z0-9_-]+$/); // URL-safe without escaping
  });

  test('limit above 100 is treated as 100', async () => {
    const { app } = setup();
    const response = await request(app).get('/payments').query({ limit: 1000 });
    expect(response.status).toBe(200);
    expect(response.body.data).toHaveLength(100);
  });

  test('a limit that is not a positive integer is a 400 problem', async () => {
    const { app } = setup();
    for (const limit of ['0', '-1', '2.5', 'abc', ''])
      expectProblem(await request(app).get('/payments').query({ limit }), 'invalid-parameter');
  });

  test('a cursor the server did not issue is a 400 problem', async () => {
    const { app } = setup();
    for (const cursor of ['abc', '20', Buffer.from('{"page":2}').toString('base64url')])
      expectProblem(await request(app).get('/payments').query({ cursor }), 'invalid-cursor');
  });
});
