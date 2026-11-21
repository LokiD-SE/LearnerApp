// Drives real Chrome (through the repo's Playwright) against the local checkout pages and writes the raw
// measurements that fe_capture.py reduces into support/fe_data/.
//
// Usage (from the repo root, Node from .nvmrc):  node practice/perf/support/fe_capture.mjs <base-url> <out-dir> [runs]
// It is NOT run by the tests or CI; the tests read the captured files.
import { chromium } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const [base, outDir, runsArg] = process.argv.slice(2);
const RUNS = Number(runsArg ?? 5);
fs.mkdirSync(outDir, { recursive: true });

const INIT = `(() => {
  const fe = (window.__fe = { lcp: null, shifts: [], fcp: null, longtasks: [], events: [] });
  const watch = (type, onEntry, extra = {}) => {
    try {
      new PerformanceObserver((list) => list.getEntries().forEach(onEntry)).observe({ type, buffered: true, ...extra });
    } catch (e) {}
  };
  watch('largest-contentful-paint', (e) => {
    fe.lcp = { startTime: e.startTime, size: e.size, url: e.url, tag: e.element ? e.element.tagName : null };
  });
  watch('layout-shift', (e) => fe.shifts.push({ startTime: e.startTime, value: e.value, hadRecentInput: e.hadRecentInput }));
  watch('paint', (e) => { if (e.name === 'first-contentful-paint') fe.fcp = e.startTime; });
  watch('longtask', (e) => fe.longtasks.push({ startTime: e.startTime, duration: e.duration }));
  watch('event', (e) => fe.events.push({ name: e.name, startTime: e.startTime, duration: e.duration, interactionId: e.interactionId || 0 }), { durationThreshold: 16 });
})();`;

const channel = process.env.PW_CHANNEL ?? 'chrome';
const browser = await chromium.launch({
  channel: channel === 'chromium' ? undefined : channel,
  headless: true,
});

async function oneRun(variant, harPath) {
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    ...(harPath ? { recordHar: { path: harPath, content: 'omit' } } : {}),
  });
  await context.addInitScript(INIT);
  const page = await context.newPage();
  await page.goto(`${base}/${variant}/`, { waitUntil: 'load' });
  await page.waitForFunction(() => performance.getEntriesByName('quote-shown').length > 0, null, {
    timeout: 15000,
  });
  await page.waitForFunction(
    () => {
      const i = document.querySelector('#hero img');
      return !!i && i.complete;
    },
    null,
    { timeout: 15000 },
  );
  await page.waitForTimeout(600); // let the late paints and long tasks settle before the one interaction
  await page.click('#pay');
  await page.waitForTimeout(400);
  const data = await page.evaluate(() => {
    const nav = performance.getEntriesByType('navigation')[0];
    const quote = performance.getEntriesByName('quote-shown')[0];
    return {
      ...window.__fe,
      nav: {
        responseStart: nav.responseStart,
        domContentLoaded: nav.domContentLoadedEventEnd,
        load: nav.loadEventEnd,
      },
      quoteShown: quote ? quote.startTime : null,
      resources: performance.getEntriesByType('resource').map((r) => ({
        name: r.name,
        startTime: r.startTime,
        requestStart: r.requestStart,
        responseStart: r.responseStart,
        responseEnd: r.responseEnd,
        transferSize: r.transferSize,
      })),
    };
  });
  await context.close(); // flushes the HAR
  return data;
}

const out = {
  meta: { browser: `Chrome ${browser.version()}`, runs: RUNS },
  slow: [],
  fixed: [],
  fixed_under_load: [],
};

for (const variant of ['slow', 'fixed']) {
  for (let i = 0; i < RUNS; i++) {
    out[variant].push(await oneRun(variant, i === 0 ? path.join(outDir, `har_${variant}_raw.json`) : null));
  }
}

// The same fixed page while 24 clients keep calling /api/quote (the backend can serve about 50 per second).
let stop = false;
const hammer = Array.from({ length: 24 }, async () => {
  while (!stop) {
    try {
      await (await fetch(`${base}/api/quote`)).arrayBuffer();
    } catch (e) {}
  }
});
await new Promise((r) => setTimeout(r, 400));
for (let i = 0; i < RUNS; i++) out.fixed_under_load.push(await oneRun('fixed', null));
stop = true;
await Promise.all(hammer);
await browser.close();
fs.writeFileSync(path.join(outDir, 'raw.json'), JSON.stringify(out));
console.log(`captured ${RUNS} runs per scenario in ${outDir}`);
