// Exercise: the caching headers of the SandPay merchant dashboard (fictional) - hashed build
// assets cached for a year, the HTML entry point revalidated on every use, and a JSON summary
// that answers a conditional GET with 304 WITHOUT building the summary.
// Tests: tests/performance/dashboard-caching.test.ts

import express, { type Express } from 'express';

export interface MerchantSummary {
  merchantId: string;
  settledMinor: number;
  currency: string;
}

export interface SummaryStore {
  /** Cheap: the summary's current version (it goes up on every change), or undefined for no such merchant. */
  version(merchantId: string): Promise<number | undefined>;
  /** Expensive: aggregates the merchant's payments. Never call it to answer a 304. */
  summary(merchantId: string): Promise<MerchantSummary>;
}

/**
 * Evaluates an If-None-Match field value against the current entity tag (RFC 9110 section 13.1.2)
 * and returns true when the condition is FALSE - that is, when the server should answer 304.
 * - `*` matches any current representation.
 * - Otherwise the value is a comma-separated list of entity tags (`"abc"` or `W/"abc"`); use the
 *   WEAK comparison (section 8.8.3.2): two tags match when their quoted parts are equal, whether or
 *   not either has the `W/` prefix.
 */
export function ifNoneMatchMatches(fieldValue: string, currentEtag: string): boolean {
  if (fieldValue.trim() === '*') return true;
  const opaque = (tag: string) => tag.replace(/^W\//, '');
  const listed = fieldValue.match(/(?:W\/)?"[^"]*"/g) ?? [];
  return listed.some((tag) => opaque(tag) === opaque(currentEtag));
}

/** Cache-Control for files whose name contains a content hash: one year, never revalidated. */
export const IMMUTABLE_ASSET = 'public, max-age=31536000, immutable';

/**
 * Builds the dashboard app (without listen()):
 * - `GET /assets/<file>` serves files from `<publicDir>/assets` with Cache-Control `IMMUTABLE_ASSET`.
 *   A file that does not exist is an ordinary 404 - it must NOT carry the one-year header.
 * - `GET /` serves `<publicDir>/index.html` with `Cache-Control: no-cache`.
 * - `GET /api/merchants/:id/summary`:
 *   - unknown merchant -> 404 `{ "error": "merchant_not_found" }` with `Cache-Control: no-store`;
 *   - the ETag is the strong tag `"<id>-v<version>"`, and every 200 and 304 carries it with
 *     `Cache-Control: private, no-cache`;
 *   - an If-None-Match that matches -> 304 with no body, and `store.summary()` is not called;
 *   - otherwise -> 200 with the summary as JSON.
 */
export function createDashboardApp(options: { store: SummaryStore; publicDir: string }): Express {
  const { store, publicDir } = options;
  const app = express();

  app.use(
    '/assets',
    express.static(`${publicDir}/assets`, { maxAge: '1y', immutable: true, fallthrough: true }),
  );

  app.get('/', (req, res) => {
    res.set('Cache-Control', 'no-cache');
    res.sendFile('index.html', { root: publicDir });
  });

  app.get('/api/merchants/:id/summary', async (req, res) => {
    const id = req.params.id;
    const version = await store.version(id);
    if (version === undefined) {
      res.set('Cache-Control', 'no-store').status(404).json({ error: 'merchant_not_found' });
      return;
    }
    const etag = `"${id}-v${version}"`;
    res.set({ ETag: etag, 'Cache-Control': 'private, no-cache' });
    const ifNoneMatch = req.get('If-None-Match');
    if (ifNoneMatch !== undefined && ifNoneMatchMatches(ifNoneMatch, etag)) {
      res.status(304).end();
      return;
    }
    res.json(await store.summary(id));
  });

  return app;
}
