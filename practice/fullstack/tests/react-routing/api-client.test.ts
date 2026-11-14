import { apiGet, ApiError } from '../../exercises/react-routing/api-client.js';

interface Call {
  url: string;
  init: RequestInit | undefined;
}

/** Replaces the global fetch with one that records each call and answers with `respond`. */
function stubFetch(respond: (call: Call) => Promise<Response>): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal('fetch', (input: string | URL | Request, init?: RequestInit) => {
    const call = { url: String(input), init };
    calls.push(call);
    return respond(call);
  });
  return calls;
}

const json = (body: unknown, status = 200, statusText = 'OK') =>
  new Response(JSON.stringify(body), { status, statusText, headers: { 'content-type': 'application/json' } });

interface Order {
  id: string;
  status: string;
}
const parseOrder = (body: unknown): Order => {
  if (typeof body === 'object' && body !== null && 'id' in body && typeof body.id === 'string') {
    return { id: body.id, status: String((body as { status?: unknown }).status) };
  }
  throw new Error('not an order');
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('apiGet', { tags: ['@exercise'] }, () => {
  it('GETs /api + path with Accept: application/json and returns the parsed body', async () => {
    const calls = stubFetch(async () => json({ id: 'ORD-1001', status: 'SUCCEEDED', extra: true }));
    const order = await apiGet('/orders/ORD-1001', { parse: parseOrder });
    expect(order).toEqual({ id: 'ORD-1001', status: 'SUCCEEDED' });
    expect(calls).toHaveLength(1);
    expect(calls[0]?.url).toBe('/api/orders/ORD-1001');
    expect(new Headers(calls[0]?.init?.headers).get('accept')).toBe('application/json');
    expect(calls[0]?.init?.method ?? 'GET').toBe('GET');
  });

  it('uses baseUrl when one is given', async () => {
    const calls = stubFetch(async () => json({ id: 'ORD-1002' }));
    await apiGet('/orders/ORD-1002', { parse: parseOrder, baseUrl: 'https://dashboard.sandpay.example/api' });
    expect(calls[0]?.url).toBe('https://dashboard.sandpay.example/api/orders/ORD-1002');
  });

  it('lets the parser reject a body of the wrong shape', async () => {
    stubFetch(async () => json({ unexpected: 'shape' }));
    await expect(apiGet('/orders/ORD-1001', { parse: parseOrder })).rejects.toThrow('not an order');
  });

  it('throws an ApiError with the Problem Details title on a 404', async () => {
    stubFetch(async () => json({ title: 'Order not found', status: 404 }, 404, 'Not Found'));
    const error = await apiGet('/orders/ORD-9999', { parse: parseOrder }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 404, title: 'Order not found', url: '/api/orders/ORD-9999' });
  });

  it('falls back to the status text when the error body is not JSON', async () => {
    stubFetch(async () => new Response('<h1>Bad gateway</h1>', { status: 502, statusText: 'Bad Gateway' }));
    const error = await apiGet('/orders', { parse: (b) => b }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 502, title: 'Bad Gateway' });
  });

  it('treats a 409 with a valid-looking JSON body as an error, not as data', async () => {
    stubFetch(async () => json({ id: 'ORD-1001' }, 409, 'Conflict'));
    await expect(apiGet('/orders/ORD-1001', { parse: parseOrder })).rejects.toBeInstanceOf(ApiError);
  });

  it('passes the AbortSignal to fetch and re-throws the abort unchanged', async () => {
    const calls = stubFetch(
      (call) =>
        new Promise<Response>((_resolve, reject) => {
          call.init?.signal?.addEventListener('abort', () =>
            reject(new DOMException('This operation was aborted', 'AbortError')),
          );
        }),
    );
    const controller = new AbortController();
    const pending = apiGet('/orders', { parse: (b) => b, signal: controller.signal });
    expect(calls[0]?.init?.signal).toBe(controller.signal);
    controller.abort();
    const error = await pending.catch((e: unknown) => e);
    expect(error).not.toBeInstanceOf(ApiError);
    expect((error as Error).name).toBe('AbortError');
  });

  it('turns a network failure into ApiError(0, "Network error")', async () => {
    stubFetch(async () => {
      throw new TypeError('fetch failed');
    });
    const error = await apiGet('/orders', { parse: (b) => b }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 0, title: 'Network error', url: '/api/orders' });
  });
});
