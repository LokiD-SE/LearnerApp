import { defineConfig, devices } from '@playwright/test';

/**
 * Settings, from environment variables:
 *   SHOP_URL    test a shop that is already running (for example the published copy) instead of serving
 *               ../shop locally
 *   SHOP_PORT   the local port (default 4310)
 *   PW_CHANNEL  "chrome" to use the installed Google Chrome instead of Playwright's Chromium
 */
const port = Number(process.env.SHOP_PORT ?? 4310);
const shopUrl = process.env.SHOP_URL;
const channel = process.env.PW_CHANNEL;

export default defineConfig({
  testDir: 'tests',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: [['list']],
  // the shop's slowest test card takes about 4 seconds; 10 s matches the Selenium framework's waits
  expect: { timeout: 10_000 },
  use: {
    baseURL: shopUrl ?? `http://127.0.0.1:${port}/`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], ...(channel ? { channel } : {}) } }],
  webServer: shopUrl
    ? undefined
    : {
        command: `node scripts/serve-shop.mjs ${port}`,
        url: `http://127.0.0.1:${port}/index.html`,
        reuseExistingServer: !process.env.CI,
      },
});
