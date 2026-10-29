import { expect, test } from '@playwright/test';

/**
 * The offline install: the manifest makes the app installable, and the service worker makes every lesson
 * - diagrams included - work without a network after the first visit. The practice shop is left alone.
 */

test.use({ serviceWorkers: 'allow' });

// One lesson per Mermaid diagram type the content uses: each type is a separate lazily loaded file.
const DIAGRAM_LESSONS = [
  'payment-lifecycle-overview', // sequenceDiagram
  'void-reversal-refund-chargeback', // flowchart
  'declines-timeouts-unknown-outcomes', // stateDiagram-v2
  'java-oop-pillars', // classDiagram
  'git-for-testers', // gitGraph
  'risk-based-testing', // quadrantChart
];

test('the manifest describes an installable app with its icons', async ({ page }) => {
  await page.goto('./');
  const href = await page.locator('link[rel="manifest"]').getAttribute('href');
  const response = await page.request.get(new URL(href!, page.url()).href);
  expect(response.ok()).toBe(true);
  const manifest = await response.json();
  expect(manifest).toMatchObject({ name: 'LearnerApp', start_url: './', scope: './', display: 'standalone' });
  const sizes = manifest.icons.map((icon: { sizes: string }) => icon.sizes);
  expect(sizes).toEqual(expect.arrayContaining(['192x192', '512x512']));
  expect(manifest.icons.some((icon: { purpose?: string }) => icon.purpose === 'maskable')).toBe(true);
  for (const icon of manifest.icons) {
    const image = await page.request.get(new URL(icon.src, response.url()).href);
    expect(image.headers()['content-type']).toBe('image/png');
  }
});

test('after the first visit every lesson and diagram works offline', async ({ page, context }) => {
  await page.goto('./');
  await expect(page.getByRole('status').filter({ hasText: 'now works offline' })).toBeVisible();
  await expect.poll(() => page.evaluate(() => navigator.serviceWorker.controller !== null)).toBe(true);

  await context.setOffline(true);
  await page.reload();
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  // The first-install message is not repeated on later visits.
  await expect(page.getByRole('status').filter({ hasText: 'now works offline' })).toHaveCount(0);

  for (const id of DIAGRAM_LESSONS) {
    await page.goto(`./#/lesson/${id}`);
    await expect(page.locator('.diagram').first()).toHaveAttribute('data-rendered', 'ok');
  }

  await page.goto('./#/search?q=idempotency');
  await expect(page.locator('.search-results').getByRole('link').first()).toBeVisible();
});

test('the practice shop is not served from the cache', async ({ page, context }) => {
  await page.goto('./');
  await expect.poll(() => page.evaluate(() => navigator.serviceWorker.controller !== null)).toBe(true);
  const cached = await page.evaluate(async () => {
    const urls: string[] = [];
    for (const name of await caches.keys()) {
      const cache = await caches.open(name);
      urls.push(...(await cache.keys()).map((request) => request.url));
    }
    return urls;
  });
  expect(cached.length).toBeGreaterThan(50);
  expect(cached.some((url) => url.includes('/shop/'))).toBe(false);

  await context.setOffline(true);
  const status = await page.evaluate(() =>
    fetch('./shop/products.json').then(
      (response) => `HTTP ${response.status}`,
      () => 'network error',
    ),
  );
  expect(status).toBe('network error');
});
