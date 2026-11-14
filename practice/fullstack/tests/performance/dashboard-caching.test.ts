import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import request from 'supertest';
import {
  createDashboardApp,
  ifNoneMatchMatches,
  type MerchantSummary,
  type SummaryStore,
} from '../../exercises/performance/dashboard-caching.js';

let publicDir: string;

beforeAll(() => {
  publicDir = mkdtempSync(join(tmpdir(), 'dashboard-public-'));
  mkdirSync(join(publicDir, 'assets'));
  writeFileSync(
    join(publicDir, 'index.html'),
    '<!doctype html><script src="/assets/index-LMGHeB4I.js"></script>',
  );
  writeFileSync(join(publicDir, 'assets', 'index-LMGHeB4I.js'), 'console.log("dashboard")');
});

afterAll(() => rmSync(publicDir, { recursive: true, force: true }));

/** An in-memory store that counts the expensive summary() calls. */
function fakeStore(versions: Record<string, number>) {
  const summaryCalls: string[] = [];
  const store: SummaryStore = {
    version: async (id) => versions[id],
    summary: async (id): Promise<MerchantSummary> => {
      summaryCalls.push(id);
      return { merchantId: id, settledMinor: 1250000, currency: 'EUR' };
    },
  };
  return { store, summaryCalls, versions };
}

describe('ifNoneMatchMatches', { tags: ['@exercise'] }, () => {
  test('uses the weak comparison of RFC 9110 section 8.8.3.2', () => {
    expect(ifNoneMatchMatches('"m_1001-v3"', '"m_1001-v3"')).toBe(true);
    expect(ifNoneMatchMatches('W/"m_1001-v3"', '"m_1001-v3"')).toBe(true);
    expect(ifNoneMatchMatches('"m_1001-v3"', 'W/"m_1001-v3"')).toBe(true);
    expect(ifNoneMatchMatches('W/"m_1001-v3"', 'W/"m_1001-v3"')).toBe(true);
    expect(ifNoneMatchMatches('"m_1001-v2"', '"m_1001-v3"')).toBe(false);
  });

  test('matches any tag in a list, and * matches anything', () => {
    expect(ifNoneMatchMatches('"a", W/"m_1001-v3", "c"', '"m_1001-v3"')).toBe(true);
    expect(ifNoneMatchMatches('"a","b"', '"m_1001-v3"')).toBe(false);
    expect(ifNoneMatchMatches('*', '"m_1001-v3"')).toBe(true);
  });

  test('compares the whole quoted tag, not a prefix or an unquoted value', () => {
    expect(ifNoneMatchMatches('"m_1001-v"', '"m_1001-v3"')).toBe(false);
    expect(ifNoneMatchMatches('m_1001-v3', '"m_1001-v3"')).toBe(false);
  });
});

describe('createDashboardApp - static files', { tags: ['@exercise'] }, () => {
  test('a hashed asset is cached for a year without revalidation', async () => {
    const res = await request(createDashboardApp({ store: fakeStore({}).store, publicDir })).get(
      '/assets/index-LMGHeB4I.js',
    );
    expect(res.status).toBe(200);
    expect(res.headers['cache-control']).toBe('public, max-age=31536000, immutable');
  });

  test('a missing asset is a 404 that no cache keeps for a year', async () => {
    const res = await request(createDashboardApp({ store: fakeStore({}).store, publicDir })).get(
      '/assets/index-OLDHASH1.js',
    );
    expect(res.status).toBe(404);
    expect(res.headers['cache-control'] ?? '').not.toContain('immutable');
    expect(res.headers['cache-control'] ?? '').not.toContain('max-age=31536000');
  });

  test('the HTML entry point is stored but revalidated every time', async () => {
    const res = await request(createDashboardApp({ store: fakeStore({}).store, publicDir })).get('/');
    expect(res.status).toBe(200);
    expect(res.headers['cache-control']).toBe('no-cache');
    expect(res.text).toContain('index-LMGHeB4I.js');
  });
});

describe('createDashboardApp - the summary API', { tags: ['@exercise'] }, () => {
  test('200 with a strong ETag built from the version, and private, no-cache', async () => {
    const { store } = fakeStore({ m_1001: 3 });
    const res = await request(createDashboardApp({ store, publicDir })).get('/api/merchants/m_1001/summary');
    expect(res.status).toBe(200);
    expect(res.headers.etag).toBe('"m_1001-v3"');
    expect(res.headers['cache-control']).toBe('private, no-cache');
    expect(res.body).toEqual({ merchantId: 'm_1001', settledMinor: 1250000, currency: 'EUR' });
  });

  test('a matching If-None-Match gets 304 with the validators, no body - and no summary is built', async () => {
    const { store, summaryCalls } = fakeStore({ m_1001: 3 });
    const res = await request(createDashboardApp({ store, publicDir }))
      .get('/api/merchants/m_1001/summary')
      .set('If-None-Match', 'W/"m_1001-v3"');
    expect(res.status).toBe(304);
    expect(res.headers.etag).toBe('"m_1001-v3"');
    expect(res.headers['cache-control']).toBe('private, no-cache');
    expect(res.text ?? '').toBe('');
    expect(summaryCalls).toEqual([]);
  });

  test('after a change the old tag no longer matches: 200 with the new tag', async () => {
    const { store, summaryCalls, versions } = fakeStore({ m_1001: 3 });
    const app = createDashboardApp({ store, publicDir });
    versions.m_1001 = 4;
    const res = await request(app).get('/api/merchants/m_1001/summary').set('If-None-Match', '"m_1001-v3"');
    expect(res.status).toBe(200);
    expect(res.headers.etag).toBe('"m_1001-v4"');
    expect(summaryCalls).toEqual(['m_1001']);
  });

  test('HEAD is conditional too', async () => {
    const { store } = fakeStore({ m_1001: 3 });
    const res = await request(createDashboardApp({ store, publicDir }))
      .head('/api/merchants/m_1001/summary')
      .set('If-None-Match', '"x", "m_1001-v3"');
    expect(res.status).toBe(304);
  });

  test('an unknown merchant is a 404 that is never stored', async () => {
    const { store } = fakeStore({ m_1001: 3 });
    const res = await request(createDashboardApp({ store, publicDir })).get('/api/merchants/m_9999/summary');
    expect(res.status).toBe(404);
    expect(res.body).toEqual({ error: 'merchant_not_found' });
    expect(res.headers['cache-control']).toBe('no-store');
  });
});
